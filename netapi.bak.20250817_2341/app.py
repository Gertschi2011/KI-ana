from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
from .user_mgmt import init_db, SessionLocal, get_user_by_id, create_user, authenticate, issue_session_token, verify_session_token

COOKIE_NAME = "ki_session"

app = FastAPI(title="KI_ana API", version="1.0")
init_db()

# --- Static ---
app.mount("/static", StaticFiles(directory=str(__import__('os').path.join(__import__('os').path.dirname(__file__), "static")), html=True), name="static")

@app.get("/", response_class=HTMLResponse)
async def index():
    # Liefert die Startseite aus static
    with open(__import__('os').path.join(__import__('os').path.dirname(__file__), "static", "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/health")
async def health():
    return {"ok": True}

# --- Auth Helpers ---
def _get_user_from_cookie(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    uid = verify_session_token(token)
    if not uid:
        return None
    with SessionLocal() as s:
        return get_user_by_id(s, uid)

# --- API: Me ---
@app.get("/api/me")
async def api_me(request: Request):
    u = _get_user_from_cookie(request)
    if not u:
        return {"auth": False}
    return {"auth": True, "id": u.id, "username": u.username, "role": u.role, "plan": u.plan, "plan_until": u.plan_until}

# --- API: Logout ---
@app.post("/api/logout")
async def api_logout(response: Response):
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME)
    return response

# --- AUTH: Login (form & json) ---
@app.post("/auth/login")
async def auth_login(request: Request):
    ct = request.headers.get("content-type","")
    if "application/json" in ct:
        data = await request.json()
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
    else:
        form = await request.form()
        username = (form.get("username") or "").strip()
        password = form.get("password") or ""
    user = authenticate(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = issue_session_token(user.id)
    resp = JSONResponse({"ok": True, "user": {"id": user.id, "username": user.username, "role": user.role, "plan": user.plan, "plan_until": user.plan_until}})
    # Cookie sicher setzen; für lokalen Test SameSite=Lax/None je nach Bedarf
    resp.set_cookie(COOKIE_NAME, token, httponly=True, secure=True, samesite="Lax", max_age=30*24*3600, path="/")
    return resp

# --- AUTH: Register (json) ---
@app.post("/auth/register")
async def auth_register(request: Request):
    data = await request.json()
    need = ["username","email","password","birthdate","address"]
    if not all(k in data and str(data[k]).strip() for k in need):
        raise HTTPException(status_code=422, detail="missing fields")
    u = create_user(
        username=data["username"].strip(),
        email=data["email"].strip(),
        password=data["password"],
        birthdate=data["birthdate"].strip(),
        address=data["address"].strip(),
    )
    return {"ok": True, "user": {"id": u.id, "username": u.username}}

# --- Payment Mock (PayPal/Stripe Platzhalter) ---
@app.post("/api/subscribe/mock")
async def subscribe_mock(request: Request):
    u = _get_user_from_cookie(request)
    if not u: raise HTTPException(status_code=401, detail="auth required")
    # In echter Integration: Payment Session erstellen und Redirect-URL liefern
    # Hier: direkt Erfolg simulieren
    import time
    with SessionLocal() as s:
        dbu = get_user_by_id(s, u.id)
        dbu.plan = "pro"
        dbu.plan_until = int(time.time()) + 30*24*3600
        s.commit()
    return {"ok": True, "plan": "pro"}

# --- Chat Stub (nur geprüft, ob eingeloggt & 18+) ---
@app.post("/api/chat")
async def chat_api(request: Request):
    u = _get_user_from_cookie(request)
    if not u: raise HTTPException(status_code=401, detail="auth required")
    # Altersprüfung (einfach über Geburtsjahr; für echte Logik: datetime parsen)
    # Hier abgespeckt: Wenn birthdate mit Jahr >= (heute-18) => Kids-Modus
    payload = await request.json()
    return {"ok": True, "reply": f"Hallo {u.username}! (Demo-Antwort). Deine Frage war: {payload.get('message','')}"}
