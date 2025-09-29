# app.py – KI_ana FastAPI (Auth, Chat, Streaming, Static)
from __future__ import annotations
import os, time, json, asyncio, re, datetime
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import date, timedelta
from netapi.core.dialog import respond_to
from netapi.core.speech import synthesize
from netapi.core.memory import search_memory

# DB / Models (vorhanden)
from .db import SessionLocal
from .models import User

# „Gehirn“, Web-Suche & Gedächtnis
from .brain import think, brain_status
status = brain_status()
from .memory_store import add_block, search_blocks, get_block, ensure_dirs
from .web_qa import web_search_and_summarize

import asyncio
from . import brain
APP_ROOT = Path(__file__).resolve().parent
STATIC_DIR = APP_ROOT / "static"
ensure_dirs()

from fastapi.middleware.cors import CORSMiddleware

# -----------------------------------------------------------------------------
# APP
# -----------------------------------------------------------------------------
app = FastAPI(title="KI_ana")
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory="netapi/static"), name="static")

# CORS-Konfiguration (vor erster Route!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ki-ana.at"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Autopilot (Scheduler): periodisches, kontrolliertes Hintergrund-Lernen
# -----------------------------------------------------------------------------
AUTOPILOT = {"running": False, "job_id": "kiana_autopilot"}
scheduler = AsyncIOScheduler()

async def _autopilot_tick():
    """Ein Tick 'Selbstleben': prüfen, lernen, speichern."""
    try:
        # delegiert an brain.autonomous_tick() – darf web_qa nutzen, memory speichern etc.
        from .brain import autonomous_tick
        await autonomous_tick()
    except Exception as e:
        print("AUTOPILOT ERROR:", e)

@app.on_event("startup")
async def _startup_autopilot():
    try:
        scheduler.start()
    except Exception:
        pass  # evtl. bereits gestartet

@app.on_event("shutdown")
async def _shutdown_autopilot():
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass

@app.post("/api/brain/autopilot/start")
async def api_autopilot_start():
    """Startet den periodischen Autopilot (alle 15 Minuten)."""
    if not AUTOPILOT["running"]:
        scheduler.add_job(_autopilot_tick, "interval", minutes=15, id=AUTOPILOT["job_id"], replace_existing=True)
        AUTOPILOT["running"] = True
    return {"ok": True, "running": True, "interval": "15m"}

@app.post("/api/brain/autopilot/stop")
async def api_autopilot_stop():
    """Stoppt den Autopilot."""
    if AUTOPILOT["running"]:
        try:
            scheduler.remove_job(AUTOPILOT["job_id"])
        except Exception:
            pass
        AUTOPILOT["running"] = False
    return {"ok": True, "running": False}

# -----------------------------------------------------------------------------
# Helpers: Secret, Sessions, Password
# -----------------------------------------------------------------------------
def _get_secret() -> str:
    s = os.getenv("KI_SECRET")
    if not s:
        # Fallback – für Dev. In Prod MUSS KI_SECRET gesetzt sein (systemd drop-in).
        s = "dev-secret-change-me"
    return s

def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_get_secret())

COOKIE_NAME = "ki_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 Tage

def _set_cookie(resp: JSONResponse, payload: Dict[str, Any]) -> None:
    token = _get_serializer().dumps(payload)
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )

def _clear_cookie(resp: JSONResponse) -> None:
    resp.delete_cookie(COOKIE_NAME, path="/")

def _read_cookie(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        data = _get_serializer().loads(token, max_age=COOKIE_MAX_AGE)
        if not isinstance(data, dict):
            return None
        return data
    except (BadSignature, SignatureExpired):
        return None

# -----------------------------------------------------------------------------
# DB Dependency
# -----------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------
class AddressIn(BaseModel):
    street: str | None = ""
    zip: str | None = ""
    city: str | None = ""
    country: str | None = ""

class BillingIn(BaseModel):
    company: str | None = ""
    vat_id: str | None = ""
    notes: str | None = ""

class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email:    EmailStr
    password: str = Field(min_length=8, max_length=200)
    birthdate: str | None = None     # "YYYY-MM-DD" oder None
    address: AddressIn | None = None
    billing: BillingIn | None = None

def _validate_birthdate(bd: str | None) -> str | None:
    if not bd:
        return None
    try:
        date.fromisoformat(bd)
        return bd
    except Exception:
        raise HTTPException(status_code=400, detail="birthdate must be YYYY-MM-DD")

class LoginIn(BaseModel):
    username: str
    password: str

class ChatIn(BaseModel):
    message: str
    lang: Optional[str] = None
    persona: Optional[str] = None

# WebSearchIn Pydantic model
class WebSearchIn(BaseModel):
    query: str

# -----------------------------------------------------------------------------
# Health + Root
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"ok": True}

# @app.get("/")
# def root_index():
#     index = STATIC_DIR / "index.html"
#     if index.exists():
#         return FileResponse(str(index))
#     return JSONResponse({"ok": True, "msg": "KI_ana backend running"})

@app.get("/api/brain/status")
def api_brain_status():
    """
    Leichter Diagnose-Snapshot aus brain.py:
    - Lern-Verzeichnisse & Queue-Zähler
    - Ob Webzugriff erlaubt ist (ALLOW_NET)
    """
    try:
        status = brain_status()
        status.update({"autopilot_running": AUTOPILOT["running"]})
        return JSONResponse({"ok": True, "status": status})
    except Exception as e:
        # Keine Interna leaken
        raise HTTPException(status_code=500, detail="brain status error")

# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
import bcrypt

def _hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def _check_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

@app.post("/api/register")
def api_register(payload: RegisterIn, db=Depends(get_db)):
    u_name = payload.username.strip()
    email = payload.email.strip().lower()
    if not u_name or not email or not payload.password:
        raise HTTPException(400, "missing fields")

    # Passwort-Policy (mind. 8 Zeichen)
    if len(payload.password) < 8:
        raise HTTPException(400, "password too short")

    # existiert schon?
    exists = db.query(User).filter(
        (User.username == u_name) | (User.email == email)
    ).first()
    if exists:
        raise HTTPException(409, "username or email already exists")

    # Geburtstdatum validieren und ggf. übernehmen
    bd = _validate_birthdate(payload.birthdate)

    # Address + Billing als JSON in users.address ablegen
    profile = {
        "address": (payload.address.dict() if payload.address else {}),
        "billing": (payload.billing.dict() if payload.billing else {}),
    }
    address_json = json.dumps(profile, ensure_ascii=False)

    user = User(
        username=u_name,
        email=email,
        password_hash=_hash_pw(payload.password),
        role="family",
        plan="free",
        plan_until=0,
        birthdate=bd,
        address=address_json,
        created_at=int(time.time()),
        updated_at=int(time.time()),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    resp = JSONResponse({"ok": True, "user": {"id": user.id, "username": user.username, "role": user.role, "plan": user.plan, "plan_until": user.plan_until}})
    _set_cookie(resp, {"uid": user.id, "ts": int(time.time())})
    return resp

@app.post("/api/login")
def api_login(payload: LoginIn, db=Depends(get_db)):
    u_name = payload.username.strip()
    user = db.query(User).filter(User.username == u_name).first()
    if not user or not _check_pw(payload.password, user.password_hash or ""):
        raise HTTPException(401, "invalid credentials")

    resp = JSONResponse({"ok": True, "user": {"id": user.id, "username": user.username, "role": user.role, "plan": user.plan, "plan_until": user.plan_until}})
    _set_cookie(resp, {"uid": user.id, "ts": int(time.time())})
    return resp

@app.get("/api/me")
def api_me(request: Request, db=Depends(get_db)):
    data = _read_cookie(request)
    if not data:
        return {"auth": False}
    uid = int(data.get("uid", 0) or 0)
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        return {"auth": False}
    return {"auth": True, "user": {"id": user.id, "username": user.username, "role": user.role, "plan": user.plan, "plan_until": user.plan_until}}

@app.post("/api/logout")
def api_logout():
    resp = JSONResponse({"ok": True})
    _clear_cookie(resp)
    return resp

# -----------------------------------------------------------------------------
# Current user helper (safe dependency for endpoints that may accept None)
# -----------------------------------------------------------------------------

def get_current_user(request: Request, db=Depends(get_db)) -> Optional[Dict[str, Any]]:
    try:
        return _require_user(request, db)
    except HTTPException:
        return None

# Helper to merge user preferences (lang/persona) into user_info
def _apply_prefs(user_info: Dict[str, Any], lang: Optional[str], persona: Optional[str]) -> Dict[str, Any]:
    # ensure we don't mutate the original dict unexpectedly
    u = dict(user_info)
    prefs = dict(u.get("prefs") or {})
    if lang:
        prefs["lang"] = lang
    if persona:
        prefs["persona"] = persona
    if prefs:
        u["prefs"] = prefs
    return u

# -----------------------------------------------------------------------------
# Helper: Normalize think() return values
# -----------------------------------------------------------------------------
def _unpack_think(result):
    """
    Normalisiert beliebige think()-Rückgaben auf:
    (answer:str, used_blocks:list|None, web_source:dict|None)
    Erlaubt: str, dict, tuple/list mit 1..4 Items.
    """
    default_blocks = []
    default_web = None

    # str -> (answer, [], None)
    if isinstance(result, str):
        return result, default_blocks, default_web

    # dict -> versuche gängige Schlüssel
    if isinstance(result, dict):
        ans = result.get("answer") or result.get("text") or result.get("reply") or ""
        blocks = result.get("used_blocks") or result.get("memory_blocks") or result.get("blocks") or default_blocks
        web = result.get("web_source") or result.get("web") or result.get("source") or default_web
        return ans, blocks, web

    # tuple/list -> verschiedene Längen akzeptieren
    if isinstance(result, (tuple, list)):
        # len==0
        if not result:
            return "", default_blocks, default_web
        # len==1: (answer,)
        if len(result) == 1:
            return result[0] or "", default_blocks, default_web
        # len==2: (answer, blocks)
        if len(result) == 2:
            return result[0] or "", result[1] or default_blocks, default_web
        # len==3: (answer, blocks, web)
        if len(result) == 3:
            return result[0] or "", result[1] or default_blocks, result[2] or default_web
        # len>=4: nimm die ersten drei
        return result[0] or "", result[1] or default_blocks, result[2] or default_web

    # Fallback
    return str(result or ""), default_blocks, default_web

# -----------------------------------------------------------------------------
# Chat (non-stream)
# -----------------------------------------------------------------------------
def _require_user(request: Request, db) -> Dict[str, Any]:
    data = _read_cookie(request)
    if not data:
        raise HTTPException(401, "login required")
    uid = int(data.get("uid", 0) or 0)
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(401, "unknown user")
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role or "family",
        "plan": user.plan or "free",
        "plan_until": int(user.plan_until or 0),
    }

@app.post("/api/chat")
def api_chat(payload: ChatIn, request: Request, db=Depends(get_db)):
    if not payload.message or not isinstance(payload.message, str) or not payload.message.strip():
        raise HTTPException(400, "message required")

    # Authenticate using a short-lived DB session to avoid holding one during SSE
    try:
        from .db import SessionLocal
        with SessionLocal() as _db:
            user_info = _require_user(request, _db)
    except HTTPException:
        raise
    # Nutzereinstellungen (optional) aus dem Payload übernehmen
    user_info = _apply_prefs(user_info, payload.lang, payload.persona)

    # Denker: Memory -> Web -> Antwort + ggf. neues Wissen ablegen
    res = think(user_info, payload.message.strip())
    answer, used_blocks, web_source = _unpack_think(res)

    # Wenn wir eine verlässliche Web-Zusammenfassung haben, ins Langzeitgedächtnis legen
    if web_source and answer:
        try:
            add_block(
                title=f"Web: {web_source.get('title') or 'Quelle'}",
                content=answer,
                tags=["web", "auto", "news" if "news" in (web_source.get("kind") or "") else "knowledge"],
                url=web_source.get("url"),
            )
        except Exception:
            pass

    return JSONResponse({
        "ok": True,
        "reply": answer or "Ich denke noch nach …",
        "sources": {
            "memory_blocks": used_blocks,
            "web": web_source
        }
    })

@app.post("/api/websearch")
def api_websearch(payload: WebSearchIn, request: Request, db=Depends(get_db)):
    # Query prüfen
    if not payload.query or not isinstance(payload.query, str) or not payload.query.strip():
        raise HTTPException(400, "query required")

    # Nutzer ermitteln (Login nötig)
    user_info = _require_user(request, db)

    # Websuche + Zusammenfassung
    try:
        result = web_search_and_summarize(payload.query.strip(), user_context=user_info)
    except Exception as e:
        # keine internen Details leaken
        raise HTTPException(500, f"web search failed: {e}")

    summary = (result or {}).get("summary")
    source = (result or {}).get("source")

    # Erkenntnisse ins Langzeitgedächtnis legen (wenn sinnvoll)
    if summary and source:
        try:
            add_block(
                title=f"Web: {source.get('title') or payload.query[:80]}",
                content=summary,
                tags=["web", "auto", "knowledge"],
                url=source.get("url"),
            )
        except Exception:
            pass

    return {"ok": True, "summary": summary, "source": source}

# -----------------------------------------------------------------------------
# Talk (non-stream)
# -----------------------------------------------------------------------------
@app.post("/api/talk")
def api_talk(payload: ChatIn, request: Request, db=Depends(get_db)):
    """
    Führt ein freies Gespräch mit KI_ana, bei Bedarf mit Web-Zugriff.
    """
    if not payload.message or not isinstance(payload.message, str) or not payload.message.strip():
        raise HTTPException(400, "message required")

    user_info = _require_user(request, db)
    user_info = _apply_prefs(user_info, payload.lang, payload.persona)

    answer = respond_to(payload.message.strip(), user_context=user_info)

    return JSONResponse({
        "ok": True,
        "reply": answer or "Ich denke noch nach …"
    })

# -----------------------------------------------------------------------------
# Talk Streaming (SSE – einfache Wort-Streams)
# -----------------------------------------------------------------------------
# ALT (falsch)
# from fastapi.responses import EventSourceResponse

# NEU (richtig)
from sse_starlette.sse import EventSourceResponse
from starlette.background import BackgroundTask
@app.get("/api/talk/stream")
async def api_talk_stream(
    request: Request,
    message: str,
    lang: str = "de",
    persona: str = "neutral",
):
    """
    Streamt eine Antwort von KI_ana mit optionalem Web-Zugriff.
    """
    # Authenticate using a short-lived DB session to avoid holding one during SSE
    try:
        from .db import SessionLocal
        with SessionLocal() as _db:
            user_info = _require_user(request, _db)
    except HTTPException:
        raise
    user_info = _apply_prefs(user_info, lang, persona)

    async def event_stream():
        yield f'data: {{"delta": "[KI_ana denkt...]"}}\n\n'

        result = respond_to(message.strip(), user_context=user_info)
        for chunk in result.split():
            yield f'data: {{"delta": "{chunk} "}}\n\n'
            await asyncio.sleep(0.05)

        yield f'data: {{"done": true}}\n\n'

    return EventSourceResponse(event_stream(), background=BackgroundTask(lambda: None))
# -----------------------------------------------------------------------------
# Favicon route
@app.get("/favicon.ico")
def favicon():
    ico = STATIC_DIR / "favicon.ico"
    if ico.exists():
        return FileResponse(str(ico))
    # fallback: 404 as JSON
    raise HTTPException(status_code=404, detail="favicon not found")

# -----------------------------------------------------------------------------
# Chat Streaming (SSE – einfache Buchstaben-Streams)
# -----------------------------------------------------------------------------
@app.get("/api/chat/stream")
async def api_chat_stream(request: Request, message: str, lang: Optional[str] = None, persona: Optional[str] = None):
    if not isinstance(message, str) or not message.strip():
        raise HTTPException(400, "message required")

    # Authenticate using a short-lived DB session to avoid holding one during SSE
    try:
        from .db import SessionLocal
        with SessionLocal() as _db:
            user_info = _require_user(request, _db)
    except HTTPException:
        raise
    user_info = _apply_prefs(user_info, lang, persona)

    async def event_generator():
        try:
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(None, lambda: think(user_info, message.strip()))
            answer, used_blocks, web_source = _unpack_think(res)
            answer = str(answer or "")
            for ch in answer:
                yield {"event": "message", "data": json.dumps({"delta": ch})}
                await asyncio.sleep(0.012)
            yield {"event": "done", "data": json.dumps({"done": True, "sources": {"memory_blocks": used_blocks, "web": web_source}})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())
# --- Autopilot: Tick auslösen (nur Creator/Admin) ---
@app.post("/api/autopilot/tick")
async def autopilot_tick(user=Depends(get_current_user)):
    if not user or user["role"] not in {"creator", "admin"}:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        result = await brain.autonomous_tick()
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# --- Autopilot: Letzten Digest abrufen ---
@app.get("/api/autopilot/last-digest")
async def autopilot_last_digest(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=403, detail="Forbidden")
    import json, os, time

    digest_path = "/home/kiana/ki_ana/learning/digest_last.json"
    if not os.path.exists(digest_path):
        return {"ok": True, "digest": None}

    with open(digest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    ts = int(os.path.getmtime(digest_path))
    return {
        "ok": True,
        "digest": data,
        "updated_at": ts,
        "updated_human": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    }


# --- Autopilot Background Scheduler ---
try:
    from fastapi_utils.tasks import repeat_every  # type: ignore
except Exception:
    # Fallback: No-Op-Decorator, falls fastapi-utils nicht installiert ist
    def repeat_every(**_kwargs):
        def _inner(func):
            return func
        return _inner

@app.on_event("startup")
@repeat_every(seconds=6*60*60)  # alle 6 Stunden
async def scheduled_autopilot_tick() -> None:
    try:
        result = await brain.autonomous_tick()
        print("[Autopilot] Tick erfolgreich:", result)
    except Exception as e:
        print("[Autopilot] Fehler beim Tick:", str(e))
# -----------------------------------------------------------------------------
# Talk API for direct message/audio response (stateless, no login required)
# -----------------------------------------------------------------------------

# New route: stateless talk endpoint (for direct message/audio response)
@app.post("/api/talk/stateless")
async def talk(payload: dict):
    user_input = payload.get("message", "")
    response = respond_to(user_input)
    audio_url = synthesize(response)
    return {"response": response, "audio_url": audio_url}

# -----------------------------------------------------------------------------
# Memory API Routen
# -----------------------------------------------------------------------------
from fastapi import Body
from netapi.core.memory_bridge import process_and_store_memory, search_memory

@app.post("/api/memory/add")
async def add_to_memory(payload: dict = Body(...)):
    text = payload.get("text", "")
    lang = payload.get("lang", "de")
    if not text:
        return {"saved": False, "error": "Text fehlt"}

    result = process_and_store_memory(text, lang)
    return result

@app.get("/api/memory/search")
async def search_memory_api(query: str, limit: int = 5):
    results = search_memory(query, limit)
    return {"query": query, "results": results}


# -----------------------------------------------------------------------------
# Neuer Endpoint: Memory-Block hinzufügen (Alternative Variante)
# -----------------------------------------------------------------------------

# save_memory_entry Funktion bereitstellen, falls nicht vorhanden
def save_memory_entry(entry: dict) -> tuple:
    try:
        from datetime import datetime
        memory_entry = {
            "timestamp": entry.get("timestamp", datetime.utcnow().isoformat()),
            "text": entry.get("text", ""),
            "importance": entry.get("importance", 0.5),
            "source": entry.get("source", "api"),
            "metadata": entry.get("metadata", {})
        }
        # Annahme: save_to_memory_store ist bereits importiert/verfügbar
        save_to_memory_store(memory_entry)
        return True, "Saved"
    except Exception as e:
        return False, str(e)


from netapi.core.memory_bridge import bridge_memory

@app.post("/api/memory/add")
async def memory_add(payload: dict):
    text = payload.get("text", "")
    lang = payload.get("lang", "de")
    result = bridge_memory(input_text=text, lang=lang)
    return result
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Chat HTML Route
# -----------------------------------------------------------------------------
@app.get("/chat.html")
async def get_chat_html():
    return FileResponse("netapi/static/chat.html")

# -----------------------------------------------------------------------------
from fastapi.responses import HTMLResponse

# HTML-Routen für statische Seiten
# -----------------------------------------------------------------------------
from pathlib import Path

@app.get("/", response_class=FileResponse)
async def index():
    index_path = Path(__file__).parent / "static" / "index.html"
    return FileResponse(index_path)

@app.get("/login", response_class=FileResponse)
def serve_login():
    return FileResponse(Path(__file__).parent / "static" / "login.html")

@app.get("/register", response_class=FileResponse)
def serve_register():
    return FileResponse(Path(__file__).parent / "static" / "register.html")

@app.get("/privacy", response_class=FileResponse)
def serve_privacy():
    return FileResponse(Path(__file__).parent / "static" / "privacy.html")

@app.get("/agb", response_class=FileResponse)
def serve_agb():
    return FileResponse(Path(__file__).parent / "static" / "agb.html")

@app.get("/about", response_class=FileResponse)
def serve_about():
    return FileResponse(Path(__file__).parent / "static" / "about.html")

@app.get("/capabilities", response_class=FileResponse)
def serve_capabilities():
    return FileResponse(Path(__file__).parent / "static" / "capabilities.html")

@app.get("/impressum", response_class=FileResponse)
def serve_impressum():
    return FileResponse(Path(__file__).parent / "static" / "impressum.html")

@app.get("/reset", response_class=FileResponse)
def serve_reset():
    return FileResponse(Path(__file__).parent / "static" / "reset.html")

@app.get("/forgot", response_class=FileResponse)
def serve_forgot():
    return FileResponse(Path(__file__).parent / "static" / "forgot.html")

@app.get("/logout", response_class=FileResponse)
def serve_logout():
    return FileResponse(Path(__file__).parent / "static" / "logout.html")

@app.get("/thanks", response_class=FileResponse)
def serve_thanks():
    return FileResponse(Path(__file__).parent / "static" / "thanks.html")

@app.get("/subscribe", response_class=FileResponse)
def serve_subscribe():
    return FileResponse(Path(__file__).parent / "static" / "subscribe.html")

@app.get("/pricing", response_class=FileResponse)
def serve_pricing():
    return FileResponse(Path(__file__).parent / "static" / "pricing.html")

@app.get("/start", response_class=FileResponse)
def redirect_start():
    return FileResponse(Path(__file__).parent / "static" / "index.html")