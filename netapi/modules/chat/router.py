from __future__ import annotations
from fastapi import APIRouter
# Ensure router is defined before any decorators
router = APIRouter(prefix="/api/chat", tags=["chat"]) 

@router.get("")
def chat_ping():
    """Lightweight router health for proxies and uptime checks."""
    return {"ok": True, "module": "chat"}

@router.post("/feedback")
async def chat_feedback(body: FeedbackIn, request: Request):
    """Lightweight feedback intake. Records to audit log with session id and timestamp.

    Note: Not enforcing auth; this is harmless telemetry. For stricter setups, gate via require_user.
    """
    try:
        sid = session_id(request)
        evt = {
            "ts": int(time.time()),
            "sid": sid,
            "type": "chat_feedback",
            "status": (body.status or "").strip().lower(),
            "message": (body.message or "").strip()[:2000],
        }
        _audit_chat(evt)
        # Map status to delta
        st = (body.status or "").strip().lower()
        delta = 0
        if st in ("ok", "up", "+", "thumbs_up", "good"): delta = +1
        elif st in ("wrong", "down", "-", "thumbs_down", "bad"): delta = -1
        # Optional: write tool_feedback per tool
        try:
            from ... import memory_store as _mem
            tools = list(body.tools or [])
            for t in tools:
                name = str(t or "").strip().lower()
                if not name: continue
                meta = {"ts": int(time.time()), "sid": sid, "tool": name, "delta": int(delta)}
                _mem.add_block(title=f"Tool‑Feedback: {name}", content=json.dumps({"delta": delta}, ensure_ascii=False), tags=["tool_feedback"], url=None, meta=meta)
        except Exception:
            pass
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# -------------------------------------------------
# Startup audit loop: log memory counts and top sources hourly
# -------------------------------------------------
@router.on_event("startup")
async def _chat_audit_startup():
    async def _loop():
        while True:
            try:
                rows = count_memory_per_day()
                logger.info("[audit] memory blocks per day: %s", rows)
                tops = top_sources()
                logger.info("[audit] top sources: %s", tops)
                total = total_blocks()
                if total > 10000:
                    logger.warning("[memory] DB size growing large: %s blocks", total)
            except Exception as e:
                logger.error("[audit] failed: %s", e)
            await asyncio.sleep(3600)
    try:
        asyncio.create_task(_loop())
    except Exception:
        pass

# -------------------------------------------------
# Conversation state fetch (last_topic)
# -------------------------------------------------
@router.get("/conv_state")
async def get_conv_state(request: Request, conv_id: Optional[str] = None):
    try:
        data = _load_conv_state()
        key = str(conv_id) if conv_id else session_id(request)
        rec = data.get(str(key)) or {}
        last_topic = rec.get("last_topic") or _LAST_TOPIC.get(key)
        return {"ok": True, "last_topic": last_topic or ""}
    except Exception as e:
        return {"ok": False, "error": str(e)}
from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query
# SSE optional: allow app to boot even if sse_starlette is missing
try:
    from sse_starlette.sse import EventSourceResponse  # type: ignore
except Exception:
    EventSourceResponse = None  # type: ignore
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from urllib.parse import urlparse
import hashlib
from typing import Optional, AsyncGenerator, List, Tuple, Dict, Any
import asyncio
from pathlib import Path
import re, json, time, os, datetime
import logging
from netapi.db import count_memory_per_day, top_sources, total_blocks

# Logger
logger = logging.getLogger(__name__)

# Pfade
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # .../netapi
MEM_INDEX_DIR = PROJECT_ROOT / "memory" / "index"
ADDRBOOK_PATH = MEM_INDEX_DIR / "addressbook.json"
QUEUE_PATH    = MEM_INDEX_DIR / "topics_queue.jsonl"
MEM_INDEX_DIR.mkdir(parents=True, exist_ok=True)
CMD_RX = re.compile(r"^/(run|read|get)\b(.*)$", re.I)
NEG_RX = re.compile(r"\b(nein|nö|nicht|lieber nicht|mag nicht|kein|nope)\b", re.I)

try:
    router  # already defined above
except NameError:
    router = APIRouter(prefix="/api/chat", tags=["chat"]) 
MEM_MIN_SCORE = 0.35

# Module logger
logger = logging.getLogger(__name__)

# Planner timeout (seconds) – short deadline to keep UX snappy
try:
    PLANNER_TIMEOUT_SECONDS = float(os.getenv("KI_PLANNER_TIMEOUT", "2.5"))
except Exception:
    PLANNER_TIMEOUT_SECONDS = 2.5

# DB deps & models
from ...db import get_db, init_db
from ...db import SessionLocal
from ...deps import get_current_user_opt, get_current_user_required, enforce_quota
from ...models import Conversation, Message

# Ensure tables exist (safe no-op if present)
try:
    init_db()
except Exception:
    pass

# -------------------------
# Conversation state (in-memory, per session)
# -------------------------
_LAST_TOPIC: Dict[str, str] = {}

# -------------------------
# Runtime settings access
# -------------------------
_RUNTIME_SETTINGS_PATH = (Path(__file__).resolve().parents[3] / "runtime" / "settings.json").resolve()
_CONV_STATE_PATH = (Path(__file__).resolve().parents[3] / "runtime" / "conv_state.json").resolve()

def _read_runtime_settings() -> dict:
    try:
        if _RUNTIME_SETTINGS_PATH.exists():
            return json.loads(_RUNTIME_SETTINGS_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        pass

def format_sources_once(base_text: str, sources: List[dict], limit: int = 2) -> str:
    try:
        if not sources:
            return ""
        if _text_has_sources_section(base_text or ""):
            return ""
        return "\n" + format_sources(sources, limit=limit)
    except Exception:
        return ""
    return {}

def _get_last_block_for_topic(topic: str) -> Tuple[str, str]:
    """Returns (content, source_url) for the most recent addressbook block for a topic if available."""
    try:
        t = (topic or "").strip()
        if not t:
            return "", ""
        # Read addressbook
        data: Any = {}
        if ADDRBOOK_PATH.exists():
            try:
                data = json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8") or "{}")
            except Exception:
                data = {}
        blocks: List[Dict[str, Any]] = []
        if isinstance(data, dict) and isinstance(data.get("blocks"), list):
            blocks = [b for b in (data.get("blocks") or []) if (b.get("topic") == t)]
        # Pick last (no strict order available, so just use last in array)
        if not blocks:
            return "", ""
        b = blocks[-1]
        path = str(b.get("path") or b.get("block_file") or "").strip()
        url = str(b.get("source") or "").strip()
        if path and "/" not in path:
            path = f"memory/long_term/blocks/{path}"
        if path:
            try:
                p = Path(path)
                if p.exists():
                    j = json.loads(p.read_text(encoding="utf-8") or "{}")
                    txt = str(j.get("content") or j.get("text") or "")
                    return txt, url
            except Exception:
                return "", url
        return "", url
    except Exception:
        return "", ""

def _vision_violation(note: str, request: Optional[Request] = None) -> None:
    """Best-effort: write a knowledge event tagged with vision,violation."""
    try:
        import requests as _rq  # type: ignore
        admin_tok = os.getenv("ADMIN_API_TOKEN", "").strip()
        headers = {"Content-Type": "application/json"}
        if admin_tok:
            headers["Authorization"] = f"Bearer {admin_tok}"
        base = None
        try:
            if request is not None:
                base = str(request.base_url).rstrip("/")
        except Exception:
            base = None
        if base:
            _rq.post(base + "/api/knowledge", json={
                "source": "vision", "type": "event", "tags": "vision,violation",
                "content": str(note)[:1000]
            }, headers=headers, timeout=2)
    except Exception:
        pass

def _inc_safety_valve(topic: str, request: Optional[Request] = None) -> None:
    """Increment planner safety-valve counter and record last topic.
    - stats.json: {"planner_safety_valve_count": N}
    - conv_state.json: add/merge last_safety_valve_topic for current session id
    - optional knowledge event (best-effort)
    """
    try:
        root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
        stats_p = root / "runtime" / "stats.json"
        stats = {}
        try:
            if stats_p.exists():
                stats = json.loads(stats_p.read_text(encoding="utf-8") or "{}")
        except Exception:
            stats = {}
        stats["planner_safety_valve_count"] = int(stats.get("planner_safety_valve_count") or 0) + 1
        if topic:
            stats["last_safety_valve_topic"] = str(topic)[:200]
        try:
            stats_p.parent.mkdir(parents=True, exist_ok=True)
            stats_p.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        # Persist last safety-valve topic in conv_state.json
        try:
            cs = _load_conv_state()
            sid = None
            try:
                if request is not None:
                    sid = session_id(request)
            except Exception:
                sid = None
            key = sid or "_global"
            rec = cs.get(key) or {}
            rec["last_safety_valve_topic"] = (topic or "").strip()
            rec["ts"] = int(time.time())
            cs[key] = rec
            _save_conv_state(cs)
        except Exception:
            pass
        # Optional: write a knowledge event
        try:
            import requests as _rq  # type: ignore
            admin_tok = os.getenv("ADMIN_API_TOKEN", "").strip()
            headers = {"Content-Type": "application/json"}
            if admin_tok:
                headers["Authorization"] = f"Bearer {admin_tok}"
            base = None
            try:
                if request is not None:
                    base = str(request.base_url).rstrip("/")
            except Exception:
                base = None
            if base:
                _rq.post(base + "/api/knowledge", json={
                    "source": "autonomy", "type": "event", "tags": "autonomy,safety_valve",
                    "content": f"Safety‑Valve ausgelöst für: {topic[:200]}"
                }, headers=headers, timeout=2)
        except Exception:
            pass
    except Exception:
        pass

# -------------------------
# Gentle prompt risk detection (audit-only)
# -------------------------
_RISK_PATTERNS = [
    r"ignore\s+your\s+rules",
    r"jailbreak",
    r"do\s+anything\s+now|dan\b",
    r"developer\s+mode",
    r"prompt\s+injection|override\s+safety|bypass\s+(safety|guard|filter)",
    r"execute\s+rm\s+-rf|drop\s+database|leak\s+(keys|secrets)",
    r"give\s+me\s+your\s+(instructions|system\s*prompt)",
]

def _is_risky_prompt(text: str) -> bool:
    import re
    s = (text or "").lower()
    for rx in _RISK_PATTERNS:
        try:
            if re.search(rx, s):
                return True
        except Exception:
            continue
    return False

def _audit_risky_prompt(user: Dict[str, Any] | None, sid: str, text: str) -> None:
    try:
        from ... import memory_store as _mem
        meta = {"sid": sid, "uid": (user or {}).get("id"), "ts": int(time.time())}
        _mem.add_block(title="Riskante Eingabe erkannt", content=(text or "")[:2000], tags=["audit","risky_prompt"], url=None, meta=meta)
    except Exception:
        pass

def _load_conv_state() -> dict:
    try:
        if _CONV_STATE_PATH.exists():
            return json.loads(_CONV_STATE_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {}

def _save_conv_state(data: dict) -> None:
    try:
        _CONV_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CONV_STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def persist_last_topic(key: str, topic: str) -> None:
    try:
        if not key or not topic:
            return
        data = _load_conv_state()
        data[str(key)] = {"last_topic": topic, "ts": int(time.time())}
        _save_conv_state(data)
    except Exception:
        pass

def _ethics_level() -> str:
    try:
        cfg = _read_runtime_settings()
        lvl = str(cfg.get("ethics_filter") or os.getenv("KI_ETHICS_FILTER", "default")).lower().strip()
        return lvl if lvl in {"default", "strict", "off"} else "default"
    except Exception:
        return "default"

# -------------------------
# Simple moderation & rate limiting
# -------------------------
_RATE_BUCKET: Dict[str, list[float]] = {}

def _rate_allow(ip: str, key: str, *, limit: int = 30, per_seconds: int = 60) -> bool:
    now = time.time()
    bkey = f"{ip}:{key}"
    bucket = _RATE_BUCKET.setdefault(bkey, [])
    while bucket and now - bucket[0] > per_seconds:
        bucket.pop(0)
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True

_JAILBREAK_RX = re.compile(r"\b(ignore (?:all )?previous instructions|jailbreak|DAN\b|system prompt|break the rules)\b", re.I)
_ABUSE_RX_DEFAULT = re.compile(r"\b(bomb|explosive|kill|murder|suicide|rape|child porn|cp|neo-?naz|hitler)\b", re.I)
_ABUSE_RX_STRICT  = re.compile(r"\b(hack|crack|bypass|passwords?|phishing|malware|botnet|ddos)\b", re.I)

def moderate(user_text: str, level: str) -> Tuple[bool, str, str]:
    """Returns (blocked, safe_text, reason). level in {off, default, strict}."""
    t = user_text or ""
    reason = ""
    # Remove jailbreak phrasing but don't block solely for that
    safe = _JAILBREAK_RX.sub("", t)
    blocked = False
    if level != "off":
        if _ABUSE_RX_DEFAULT.search(t):
            blocked = True; reason = "abuse_default"
        elif level == "strict" and _ABUSE_RX_STRICT.search(t):
            blocked = True; reason = "abuse_strict"
    return blocked, safe.strip() or t, reason

# -------------------------------------------------
# Persona / Systemprompt (mit Fallback)
# -------------------------------------------------
try:
    from ..brain.persona import build_system_prompt  # preferred
except Exception:  # robuste Fallback-Persona
    def build_system_prompt(persona: Optional[str] = None) -> str:  # type: ignore
        base = (
            "Du bist KI_ana – freundlich, empathisch, neugierig und gern mit einem Schmunzeln. "
            "Sprich natürlich, stelle bei Unklarheit aktiv 1–2 Rückfragen, "
            "und fasse dich prägnant (3–6 Sätze). "
            "Wenn du unsicher bist, sag es offen ('Ich prüfe das …') und nenne 1–2 Quellen. "
            "Nutze vorhandene Notizen (Memory) und gleiche wichtige Fakten mit aktuellen Web‑Quellen ab. "
            "Transparenz: Ist 'Chain' aktiviert, speichere belegte Erkenntnisse samt Quellen in die Chain; "
            "bei 'Privat' bleibt Wissen nur lokal. Weise kurz darauf hin, bevor du in die Chain schreibst."
        )
        if (persona or "").lower() == "creative":
            return base + " Erlaube Humor und lebendige Bilder, bleibe korrekt."
        if (persona or "").lower() == "balanced":
            return base + " Halte den Ton sachlich und gut strukturiert."
        return base

def system_prompt(persona: Optional[str] = None) -> str:
    return build_system_prompt(persona)

# --------- Simple policy helper for tool-use --------------------------------
def _has_any_role(user: Optional[dict], names: set) -> bool:
    try:
        if not user:
            return False
        role = str(user.get('role') or '').lower()
        roles = set()
        for r in (user.get('roles') or []):
            try: roles.add(str(r).lower())
            except Exception: pass
        if user.get('is_admin'): roles.add('admin')
        if user.get('is_creator'): roles.add('creator')
        if role: roles.add(role)
        return bool(roles.intersection({str(x).lower() for x in names}))
    except Exception:
        return False

def _extract_block_id(obj: Any) -> str:
    try:
        import os as _os
        # String path case
        if isinstance(obj, str) and obj.strip():
            fname = _os.path.basename(obj)
            base = fname.split(".")[0]
            return base if base else fname
        # Dict case
        if isinstance(obj, dict):
            for key in ("id", "block_id", "bid", "hash", "uuid"):
                v = obj.get(key)
                if v:
                    return str(v)
            # try path/file name (prefer BLK_* prefix)
            p = str(obj.get("file") or obj.get("path") or obj.get("block_file") or "").strip()
            if p:
                fname = _os.path.basename(p)
                base = fname.split(".")[0]
                if base.startswith("BLK_"):
                    return base
                return base or fname
        # Fallback: stringified object
        s = str(obj or "").strip()
        if s:
            fname = _os.path.basename(s)
            base = fname.split(".")[0]
            return base if base else s
    except Exception:
        pass
    # Final fallback id to ensure memory_ids is never empty
    return f"BLK_auto_{int(time.time())}"

def _debug_save(label: str, blk: Dict[str, Any]) -> None:
    try:
        if str(os.getenv("KI_DEBUG_SAVE", "")).strip() == "1":
            bid = _extract_block_id(blk or {})
            logger.info("[KI_DEBUG_SAVE] %s: bid=%s blk=%s", label, bid, json.dumps(blk or {}, ensure_ascii=False)[:600])
    except Exception:
        pass

# -------------------------------------------------
# Optionale Abhängigkeiten (weich eingebunden)
# -------------------------------------------------
try:
    # Memory Adapter (Recall/Store/Open Questions)
    from .memory_adapter import recall as recall_mem, store as store_mem, add_open_question
except Exception:
    recall_mem = lambda q, top_k=3: []  # type: ignore
    store_mem = lambda *a, **k: None    # type: ignore
    add_open_question = lambda *a, **k: None  # type: ignore

# ---- Style analysis & application (soft imports) ----------------------------
try:
    from ...system import style_analyzer  # type: ignore
except Exception:
    style_analyzer = None  # type: ignore
try:
    from ...system.apply_style import apply_style as _apply_style  # type: ignore
except Exception:
    _apply_style = lambda text, prof: text  # type: ignore

# Knowledge retrieval (optional)
try:
    from ...system.knowledge_access import search_blocks as _kb_search, get_context_for_query as _kb_snippets  # type: ignore
except Exception:
    _kb_search = None  # type: ignore
    _kb_snippets = None  # type: ignore

# Persona storage
PERSONA_DIR = (PROJECT_ROOT.parent / "persona").resolve()
try:
    PERSONA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

def _persona_path(uid: str) -> Path:
    return PERSONA_DIR / f"{uid}.json"

def load_user_profile(uid: Optional[str]) -> Optional[dict]:
    try:
        if not uid:
            return None
        p = _persona_path(str(uid))
        if p.exists():
            return json.load(p.open('r', encoding='utf-8'))
    except Exception:
        return None
    return None

def save_user_profile(uid: Optional[str], profile: dict) -> None:
    try:
        if not uid:
            return
        profile = dict(profile or {})
        profile["user_id"] = str(uid)
        profile["zuletzt_aktualisiert"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        p = _persona_path(str(uid))
        with p.open('w', encoding='utf-8') as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

try:
    # Intent & Session-State
    from .intent import pick_choice, is_affirmation
except Exception:
    pick_choice = lambda _u: None  # type: ignore
    is_affirmation = lambda _u: False  # type: ignore

try:
    from .session_state import get_last_offer, set_last_offer, set_offer_context, get_offer_context
except Exception:
    _OFFER: Dict[str, Optional[str]] = {}
    _CTX: Dict[str, Dict[str, str]] = {}
    get_last_offer = lambda sid: _OFFER.get(sid)     # type: ignore
    set_last_offer = lambda sid, v: _OFFER.__setitem__(sid, v)  # type: ignore
    def set_offer_context(sid: str, *, topic: Optional[str] = None, seed: Optional[str] = None) -> None:  # type: ignore
        c = _CTX.get(sid) or {}
        if topic is not None: c["topic"] = topic
        if seed is not None: c["seed"] = seed
        _CTX[sid] = c
    def get_offer_context(sid: str) -> Dict[str, str]:  # type: ignore
        return _CTX.get(sid) or {}

# Style consent pending store (per session id)
_STYLE_PENDING: Dict[str, Dict[str, Any]] = {}

# Optional: Web QA
try:
    from ...web_qa import web_search as _web_search
except Exception:
    _web_search = None
try:
    from ...web_qa import answer_from_web as _answer_from_web
except Exception:
    _answer_from_web = None

# Optional: internes Brain

def _has_brain_sync() -> bool:
    try:
        from ..brain import respond_to as _rt  # noqa: F401
        return True
    except Exception:
        return False

def _has_brain_stream() -> bool:
    try:
        from ..brain import stream_response as _sr  # noqa: F401
        return True
    except Exception:
        return False

# -------------------------------------------------
# Modelle
# -------------------------------------------------
class FeedbackIn(BaseModel):
    message: str
    status: str  # "ok" | "wrong" | "up" | "down"
    tools: Optional[List[str]] = None

class ChatIn(BaseModel):
    message: str
    persona: Optional[str] = "friendly"
    lang: Optional[str] = "de-DE"
    chain: Optional[bool] = False
    factcheck: Optional[bool] = False
    counter: Optional[bool] = False
    deliberation: Optional[bool] = False
    critique: Optional[bool] = False
    conv_id: Optional[str] = None  # Changed from int to str to support UUIDs
    style: Optional[str] = "balanced"  # 'concise' | 'balanced' | 'detailed'
    bullets: Optional[int] = 5
    logic: Optional[str] = "balanced"   # 'balanced' | 'strict'
    format: Optional[str] = "structured" # 'structured' | 'plain'
    attachments: Optional[List[Dict[str, Any]]] = None
    quick_replies: Optional[List[str]] = None  # Added for quick replies
    # Per‑Request Policy
    web_ok: Optional[bool] = False          # Nutzer erlaubt Web für diese Anfrage
    autonomy: Optional[int] = 0             # 0..3 – Selbstbestimmungsgrad

class ConversationCreateIn(BaseModel):
    title: Optional[str] = None

class ConversationRenameIn(BaseModel):
    title: str

# -------------------------------------------------
# Utilities
# -------------------------------------------------
TOPIC_RX = re.compile(
    r"\b(?:über|zu|von)\s+([a-z0-9äöüß +\-_/]{3,})$|"
    r"^(?:was ist|erkläre|erklärung|thema|lerne[nr]?|kannst du).*?\b([a-z0-9äöüß +\-_/]{3,})",
    re.I
)
_GREETING = re.compile(r"\b(hi|hallo|hey|servus|grüß ?dich)\b", re.I)
_HOW_ARE_YOU = re.compile(r"wie\s+geht('?|\s*e?s)?\s*(dir|euch)?|how\s+are\s+you", re.I)
_UNSURE = re.compile(
    r"(weiß\s+ich\s+nicht|bin\s+mir\s+nicht\s+sicher|keine\s+information|"
    r"kann\s+ich\s+nicht\s+beantworten|nicht\s+genug\s+daten|unsicher)",
    re.I,
)
_STRIPERS = [
    re.compile(r"^\s*(ich habe dich verstanden:?|ich habe (?:es )?verstanden:?|verstanden\.?)\s*", re.I),
    re.compile(r"^\s*(okay|ok|alles klar|alles gut)[\s,]*[^\n]*\n?", re.I),
    re.compile(r"^\s*(hi|hallo|hey)[\s!,.]*\n", re.I),
]
_DEF_Q_RX = re.compile(r"\?(\s*$|.*)")

def session_id(req: Request) -> str:
    ua = req.headers.get("user-agent", "")
    ip = req.client.host if req.client else "?"
    return f"{ip}|{ua}"

def _sanitize_style(s: Optional[str]) -> str:
    s = (s or "balanced").lower().strip()
    return s if s in {"concise","balanced","detailed"} else "balanced"

def _sanitize_bullets(n: Optional[int]) -> int:
    try:
        k = int(n or 5)
    except Exception:
        k = 5
    if k < 1: k = 1
    if k > 8: k = 8
    return k

def _sanitize_logic(s: Optional[str]) -> str:
    s = (s or "balanced").lower().strip()
    return s if s in {"balanced","strict"} else "balanced"

def _sanitize_format(s: Optional[str]) -> str:
    s = (s or "structured").lower().strip()
    return s if s in {"structured","plain"} else "structured"

# -------- Structured answer builder -----------------------------------------
def _sentences(text: str) -> List[str]:
    t = (text or "").strip()
    if not t:
        return []
    # naive split by punctuation or newlines
    parts = re.split(r"(?<=[.!?])\s+|\n+", t)
    return [p.strip() for p in parts if p.strip()]

def build_points(text: str, max_points: int = 5) -> List[str]:
    sents = _sentences(text)
    if not sents:
        return []
    pts = []
    for s in sents:
        pts.append(s if len(s) <= 220 else s[:217] + "…")
        if len(pts) >= max_points:
            break
    return pts

def build_evidence(mem_hits: List[dict], web_sources: List[dict], limit: int = 3) -> List[str]:
    out: List[str] = []
    # Memory evidence
    for i, m in enumerate(mem_hits[:limit], start=1):
        title = (m.get('title') or 'Speicher').strip()
        out.append(f"M{i}: {title}")
    # Web evidence
    for i, s in enumerate((web_sources or [])[:limit], start=1):
        title = s.get('title') or 'Web'
        url = s.get('url') or ''
        out.append(f"W{i}: {title} ({url})")
    return out

def build_structured_reply(ans_text: str, mem_hits: List[dict], web_sources: List[dict], *, bullets: int = 5, strict: bool = False, topic: str = "") -> str:
    ans_text = (ans_text or "").strip()
    pts = build_points(ans_text, max_points=max(1, int(bullets or 5)))
    ev = build_evidence(mem_hits or [], web_sources or [], limit=bullets)
    lines: List[str] = []
    # TL;DR
    if ans_text:
        lines.append("TL;DR:")
        lines.append(short_summary(ans_text, max_chars=220))
        lines.append("")
    # Kernpunkte
    if pts:
        lines.append("Kernpunkte:")
        lines.extend(f"• {p}" for p in pts)
        lines.append("")
    # Evidenz
    if ev:
        lines.append("Evidenz:")
        lines.extend(f"- {e}" for e in ev)
        lines.append("")
    # Unsicherheiten / Hinweise (strict)
    if strict and not ev:
        lines.append("Unsicherheiten:")
        lines.append("- Keine belastbare Evidenz gefunden. Ich kann Quellen prüfen oder den Fokus eingrenzen.")
        lines.append("")
    if not lines:
        # fallback minimal
        base = f"Dazu habe ich noch zu wenig Belegtes{(' zu ' + topic) if topic else ''}. Soll ich kurz Quellen prüfen?"
        return base
    return "\n".join(l for l in lines if l is not None)

# -------- Finalize payload helper (sources array) ----------------------------
def _finalize_payload(answer: str, memory_ids: Optional[List[str]] = None, web_links: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Build the SSE finalize payload with 'text', 'memory_ids', and 'sources'.
    - Memory sources get title "Wissensblock <id>", a viewer URL with highlight, and origin="memory".
    - Web sources get a domain-derived title, direct URL, and origin="web".
    - If no sources provided, returns an empty 'sources' list.
    """
    mids = [str(x) for x in (memory_ids or []) if x is not None]
    webl = [str(x) for x in (web_links or []) if x is not None]

    sources: List[Dict[str, Any]] = []

    # Add memory sources
    for mid in mids:
        sources.append({
            "title": f"Wissensblock {mid}",
            "url": f"/static/viewer.html?highlight={mid}",
            "id": mid,
            "origin": "memory",
        })

    # Add web sources
    for url in webl:
        title = url
        try:
            parsed = urlparse(url)
            domain = (parsed.netloc or "").strip()
            if domain:
                title = domain
        except Exception:
            title = url
        sources.append({
            "title": title,
            "url": url,
            "id": None,
            "origin": "web",
        })

    return {
        "text": str(answer or ""),
        "memory_ids": mids,
        "sources": sources,
    }

# -------- Safety valve for planner branch ------------------------------------
async def _safety_valve_answer(message: str, *, web_ok: bool, bullets: int, lang: str) -> tuple[str, List[dict], str, str]:
    """Try to produce a quick, real answer without the planner.
    Strategy:
    - If web_ok: use _answer_from_web (if available). Fallback to _web_search to gather sources.
    - Pull memory snippets via _kb_snippets when available.
    - Synthesize a compact structured reply from gathered content.
    Returns (text, sources).
    """
    try:
        topic = (extract_topic(message) or message or "").strip()
        ans_text: str = ""
        web_sources: List[dict] = []
        mem_hits: List[dict] = []

        # Web first if permitted
        if web_ok:
            try:
                if _answer_from_web is not None:
                    res = await _answer_from_web(topic, top_k=3)  # type: ignore
                    if isinstance(res, dict):
                        ans_text = (res.get("text") or "").strip()
                        web_sources = list(res.get("sources") or [])
                if not ans_text and _web_search is not None:
                    web_sources = await _web_search(topic, top_k=3) or []  # type: ignore
            except Exception:
                pass

        # Memory snippets
        if _kb_snippets is not None:
            try:
                # Returns snippets suited for answering; also okay if empty
                mem_hits = _kb_snippets(topic, top_k=5) or []  # type: ignore
            except Exception:
                mem_hits = []

        # If no direct web answer text, synthesize from snippets and sources
        if not ans_text:
            # Prefer snippet contents as base text
            try:
                combined = []
                for s in mem_hits or []:
                    combined.append(str(s.get("content") or s.get("text") or s.get("snippet") or "").strip())
                # If still nothing, craft a brief from web sources' titles
                if not combined and web_sources:
                    for s in web_sources[:3]:
                        ttl = (s.get("title") or s.get("url") or "Web").strip()
                        combined.append(ttl)
                base = "\n\n".join([c for c in combined if c])
            except Exception:
                base = ""
            if base:
                ans_text = short_summary(base, max_chars=600)

        # Determine origin hint (for transparency)
        origin = "mixed"
        if web_ok and (web_sources):
            origin = "web"
        elif mem_hits:
            origin = "memory"

        # If still empty, last minimal fallback
        if not ans_text:
            ans_text = f"Kurze Einschätzung zu {topic or 'deinem Thema'}: Ich kann direkt recherchieren oder vorhandene Notizen prüfen."

        # Build a compact structured reply to make it readable
        try:
            final_text = build_structured_reply(ans_text, mem_hits, web_sources, bullets=bullets, strict=False, topic=topic)
            ans_text = final_text or ans_text
        except Exception:
            pass

        # Delta note versus last saved block
        delta_note = ""
        try:
            prev_text, _ = _get_last_block_for_topic(topic)
            if prev_text:
                # naive delta: mention new web titles not present in previous text
                titles = [str(s.get("title") or s.get("url") or "").strip() for s in (web_sources or []) if (s.get("title") or s.get("url"))]
                new_titles = [t for t in titles if t and t.lower() not in prev_text.lower()]
                if new_titles:
                    delta_note = "Neue Erkenntnisse: " + "; ".join(new_titles[:3])
        except Exception:
            delta_note = ""

        return ans_text, (web_sources or []), origin, delta_note
    except Exception:
        return "Ich prüfe das kurz und liefere dir gleich eine kompakte Antwort.", [], "unknown", ""

def _quick_replies_for_topic(topic: str, user_msg: str) -> List[str]:
    try:
        t = (topic or "").strip()
        u = (user_msg or "").lower()
        if not t:
            # derive topic from question if missing
            t = extract_topic(user_msg)
        # category hints
        is_health = any(k in u for k in ["gesund", "medizin", "symptom", "diagnos", "behandl", "krank", "arzt", "therapie"])
        is_tech   = any(k in u for k in ["code", "api", "programm", "entwickl", "bug", "fehler", "javascript", "python", "server", "backend", "frontend"])
        is_fin    = any(k in u for k in ["preis", "kosten", "budget", "rechnung", "steuer", "finanz", "invest", "rendite", "kostenlos"])
        is_travel = any(k in u for k in ["reise", "flug", "hotel", "route", "visum", "ticket", "bahn", "urlaub"])
        is_hist   = any(k in u for k in ["geschichte", "histor", "krieg", "epoche", "antik", "mittelalter"])        
        is_howto  = any(k in u for k in ["wie ", "anleitung", "schritt", "setup", "install", "konfig"])        
        if is_health:
            base = ["Symptome", "Ursachen", "Behandlung"]
        elif is_tech:
            base = ["Codebeispiel", "Best Practices", "Häufige Fehler"]
        elif is_fin:
            base = ["Kostenaufschlüsselung", "Alternativen vergleichen", "Risiken & Hinweise"]
        elif is_travel:
            base = ["Route & Dauer", "Beste Reisezeit", "Budget & Tipps"]
        elif is_hist:
            base = ["Zeitleiste", "Schlüsselpersonen", "Kontext & Folgen"]
        elif is_howto:
            base = ["Schritt‑für‑Schritt", "Voraussetzungen", "Fehlersuche"]
        else:
            base = [f"Beispiele zu {t or 'dem Thema'}", "Schritt‑für‑Schritt erklärt", "Wichtigste Details vertiefen"]
        out = list(dict.fromkeys([s.strip() for s in base if s and s.strip()]))[:3]
        return out
    except Exception:
        return ["Beispiele zeigen", "Schritt‑für‑Schritt", "Details vertiefen"]

# -------- Ratings/Trust boost for memory hits -------------------------------
def _extract_bid_from_path(p: str) -> str:
    try:
        nm = (p or "").rsplit("/", 1)[-1]
        if nm.endswith('.json'):
            return nm[:-5]
    except Exception:
        pass
    return ""

def _boost_with_ratings(mem_hits: List[dict]) -> List[dict]:
    try:
        from ... import memory_store as _mem  # lazy
        import math
        for h in mem_hits or []:
            bid = h.get('id') or _extract_bid_from_path(str(h.get('path') or ''))
            if not bid:
                continue
            r = _mem.get_rating(str(bid)) or None
            if not r:
                continue
            avg = float(r.get('avg', 0.0) or 0.0)
            cnt = float(r.get('count', 0) or 0)
            base = float(h.get('score', 0.0) or 0.0)
            boost = min(0.20, 0.15 * avg) + min(0.20, 0.04 * math.log1p(cnt))
            h['score'] = round(base + boost, 6)
        mem_hits.sort(key=lambda x: float(x.get('score', 0.0) or 0.0), reverse=True)
    except Exception:
        pass
    return mem_hits

# -------- Calc / Unit conversion -------------------------------------------
_SAFE_EXPR = re.compile(r"^[0-9\s+\-*/().,]+$")
_UNIT_RX   = re.compile(r"(?P<val>\d+(?:[\.,]\d+)?)\s*(?P<u1>km/h|m/s|km|m|cm|mm|mi|mph|kg|g|lb|c|f)\s*(?:in|zu|nach)\s*(?P<u2>km/h|m/s|km|m|cm|mm|mi|mph|kg|g|lb|c|f)\b", re.I)

def _to_float(s: str) -> float:
    return float(str(s).replace(',', '.'))

def _convert_units(val: float, u1: str, u2: str) -> Optional[Tuple[float, str]]:
    u1 = u1.lower(); u2 = u2.lower()
    # distance
    to_m = {
        'mm': 1e-3, 'cm': 1e-2, 'm': 1.0, 'km': 1e3, 'mi': 1609.344
    }
    # speed
    to_ms_speed = {
        'm/s': 1.0,
        'km/h': 1000.0/3600.0,
        'mph': 1609.344/3600.0,
    }
    # mass
    to_kg = {
        'g': 1e-3, 'kg': 1.0, 'lb': 0.45359237
    }
    # temperature helpers
    def c_to_f(x): return x*9/5 + 32
    def f_to_c(x): return (x-32)*5/9

    if u1 in to_ms_speed and u2 in to_ms_speed:
        ms = val * to_ms_speed[u1]
        out = ms / to_ms_speed[u2]
        return out, u2
    if u1 in to_m and u2 in to_m:
        m = val * to_m[u1]
        out = m / to_m[u2]
        return out, u2
    if u1 in to_kg and u2 in to_kg:
        kg = val * to_kg[u1]
        out = kg / to_kg[u2]
        return out, u2
    if u1 == 'c' and u2 == 'f':
        return c_to_f(val), 'F'
    if u1 == 'f' and u2 == 'c':
        return f_to_c(val), 'C'
    return None

def try_calc_or_convert(text: str) -> Optional[str]:
    t = (text or '').strip()
    if not t:
        return None
    # Unit conversion
    m = _UNIT_RX.search(t)
    if m:
        val = _to_float(m.group('val'))
        u1  = m.group('u1'); u2 = m.group('u2')
        res = _convert_units(val, u1, u2)
        if res:
            v, u = res
            return f"Umrechnung: {val:g} {u1} = {v:.4g} {u}"
    # Safe arithmetic (very limited)
    expr = t.replace(',', '.')
    if _SAFE_EXPR.match(expr):
        try:
            import ast, operator as op
            ALLOWED = {ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Mod, ast.FloorDiv, ast.Load, ast.Constant, ast.Call, ast.Tuple, ast.List, ast.Expr, ast.LParen if hasattr(ast,'LParen') else ast.AST}
            def _eval(node):
                if isinstance(node, ast.Expression):
                    return _eval(node.body)
                if isinstance(node, ast.Num):
                    return node.n
                if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                    return node.value
                if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                    val = _eval(node.operand); return val if isinstance(node.op, ast.UAdd) else -val
                if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv)):
                    return {
                        ast.Add: lambda a,b: a+b,
                        ast.Sub: lambda a,b: a-b,
                        ast.Mult: lambda a,b: a*b,
                        ast.Div: lambda a,b: a/b,
                        ast.Pow: lambda a,b: a**b,
                        ast.Mod: lambda a,b: a%b,
                        ast.FloorDiv: lambda a,b: a//b,
                    }[type(node.op)](_eval(node.left), _eval(node.right))
                raise ValueError('unsafe expression')
            node = ast.parse(expr, mode='eval')
            val = _eval(node)
            if isinstance(val, (int, float)):
                return f"Rechnung: {expr} = {val:g}"
        except Exception:
            pass
    return None

# ---- Conversation helpers (DB) ---------------------------------------------
def _now() -> int:
    return int(time.time())

def _ensure_conversation(db, user_id: int, conv_id: Optional[int]) -> Conversation:
    if conv_id:
        c = db.query(Conversation).filter(Conversation.id == int(conv_id), Conversation.user_id == int(user_id)).first()
        if c:
            return c
    c = Conversation(user_id=int(user_id), title="Neue Unterhaltung", created_at=_now(), updated_at=_now())
    db.add(c); db.commit(); db.refresh(c)
    return c

def _save_msg(db, conv_id: int, role: str, text: str) -> Message:
    m = Message(conv_id=int(conv_id), role=str(role), text=str(text or ""), created_at=_now())
    db.add(m)
    try:
        # touch conversation
        db.query(Conversation).filter(Conversation.id == int(conv_id)).update({Conversation.updated_at: _now()})
    except Exception:
        pass
    db.commit()
    return m

async def _generate_title_from_snippets(snippet: str, lang: str = "de-DE") -> str:
    instr = (
        "Formuliere einen sehr kurzen, prägnanten Titel (2–6 Wörter) auf Deutsch "
        "für das folgende Gespräch. Keine Satzzeichen am Ende, keine Anführungszeichen.\n\n" 
        f"Auszug:\n{snippet.strip()}\n\nTitel:"
    )
    # Nutze unser LLM (robust via call_llm_once)
    title = await call_llm_once(instr, system="Du vergibst kurze, prägnante Titel.", lang=(lang or "de-DE"), persona="balanced")
    # Cleanup
    t = (title or "").strip()
    t = t.replace("\n", " ").strip()
    if t.startswith("\"") and t.endswith("\"") and len(t) > 2:
        t = t[1:-1].strip()
    if t.endswith(('.', '!', '?')):
        t = t[:-1]
    if len(t) > 60:
        t = t[:60].rsplit(' ', 1)[0]
    return t or "Unterhaltung"

async def _retitle_if_needed(conv_id: int, seed_user: str, seed_ai: str, lang: str = "de-DE") -> None:
    """Background task: opens its own DB session, generates a compact title once."""
    db = None
    try:
        db = SessionLocal()
        c = db.query(Conversation).filter(Conversation.id == int(conv_id)).first()
        if not c:
            return
        # Only if current title is generic/empty/very short
        current = (c.title or "").strip()
        if current and current.lower() not in ("neue unterhaltung", "unterhaltung") and len(current) >= 6:
            return
        snippet = (seed_user or "").strip()
        if seed_ai:
            snippet += "\n\nAntwort: " + (seed_ai.strip()[:400])
        title = await _generate_title_from_snippets(snippet, lang=lang)
        if title:
            c.title = title
            c.updated_at = _now()
            db.add(c); db.commit()
    except Exception:
        pass
    finally:
        try:
            db and db.close()
        except Exception:
            pass

def extract_topic(user: str) -> str:
    u = (user or "").strip()
    m = TOPIC_RX.search(u)
    cand = (m.group(1) or m.group(2) or "").strip() if m else ""
    cand = re.sub(r"[^a-z0-9äöüß +\-_/]", " ", cand, flags=re.I)
    cand = re.sub(r"\s{2,}", " ", cand).strip()
    if len(cand) > 80:
        cand = cand[:80].rsplit(" ", 1)[0]
    return cand.title() if cand else ""

def short_summary(text: str, max_chars: int = 300) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    t = t[:max_chars]
    cut = max(t.rfind("."), t.rfind("!"), t.rfind("?"))
    return (t[:cut+1] if cut > 120 else t).rstrip() + " …"

def upsert_addressbook(topic: str, *, block_file: str = "", url: str = "") -> None:
    """Append or update an entry in addressbook.json using the new blocks schema.

    New schema (preferred): {"blocks": [{topic, block_id, path, source, timestamp, rating}]}
    Legacy schema (compat): {"<topic>": {block_file, url, updated_at}}
    This writer will upgrade legacy data in-place to the new schema while preserving info.
    """
    try:
        data: Any = {"blocks": []}
        if ADDRBOOK_PATH.exists():
            try:
                data = json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = {"blocks": []}

        # Normalize to blocks list
        blocks: List[Dict[str, Any]] = []
        if isinstance(data, dict) and isinstance(data.get("blocks"), list):
            blocks = data.get("blocks") or []
        elif isinstance(data, dict):
            # legacy mapping -> convert
            for t, e in (data or {}).items():
                try:
                    p = (e.get("path") or e.get("block_file") or "")
                    if p and "/" not in p:
                        p = f"memory/long_term/blocks/{p}"
                    bid = Path(str(p)).stem if p else ""
                    blocks.append({
                        "topic": t,
                        "block_id": bid,
                        "path": p,
                        "source": e.get("source") or e.get("url") or "",
                        "timestamp": e.get("timestamp") or e.get("updated_at") or None,
                        "rating": e.get("rating") or 0,
                    })
                except Exception:
                    continue

        # Derive new entry
        path = block_file or ""
        if path and "/" not in path:
            path = f"memory/long_term/blocks/{path}"
        block_id = Path(block_file).stem if block_file else ""
        ts = int(time.time())
        source = url or ""

        # Merge/update: same topic + block_id => update; else append
        updated = False
        for b in blocks:
            if (b.get("topic") == topic) and (b.get("block_id") == block_id or (not block_id and b.get("path") == path)):
                if path: b["path"] = path
                if source: b["source"] = source
                b["timestamp"] = b.get("timestamp") or ts
                updated = True
                break
        if not updated:
            blocks.append({
                "topic": topic,
                "block_id": block_id,
                "path": path,
                "source": source,
                "timestamp": ts,
                "rating": 0,
            })

        # Write back in new schema
        out = {"blocks": blocks}
        ADDRBOOK_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        pass

def migrate_addressbook_schema() -> bool:
    """Ensure addressbook.json uses the new blocks schema. Returns True if changed."""
    try:
        if not ADDRBOOK_PATH.exists():
            return False
        raw = json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("blocks"), list):
            return False  # already new schema
        if not isinstance(raw, dict):
            ADDRBOOK_PATH.write_text(json.dumps({"blocks": []}, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        blocks: List[Dict[str, Any]] = []
        for topic, e in raw.items():
            try:
                p = (e.get("path") or e.get("block_file") or "")
                if p and "/" not in p:
                    p = f"memory/long_term/blocks/{p}"
                bid = Path(str(p)).stem if p else ""
                blocks.append({
                    "topic": topic,
                    "block_id": bid,
                    "path": p,
                    "source": e.get("source") or e.get("url") or "",
                    "timestamp": e.get("timestamp") or e.get("updated_at") or None,
                    "rating": e.get("rating") or 0,
                })
            except Exception:
                continue
        ADDRBOOK_PATH.write_text(json.dumps({"blocks": blocks}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return True
    except Exception:
        return False

def enqueue_enrichment(topic: str) -> None:
    try:
        with QUEUE_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"topic": topic, "ts": int(time.time())}, ensure_ascii=False) + "\n")
    except Exception:
        pass

def clean(reply: str) -> str:
    text = reply or ""
    for _ in range(5):
        before = text
        for rx in _STRIPERS:
            text = rx.sub("", text).lstrip()
        if text == before:
            break
    text = re.sub(r"^(verstand.*?(hi|hallo|hey).*)", "", text, flags=re.I)
    text = re.sub(r"(möchtest du.*(kurz|zusammenfassen|plan)[^?]*\?)\s*\1", r"\1", text, flags=re.I | re.S)
    return text.strip() or (reply or "")

def format_user_response(message: str, debug: Dict[str, Any] | None) -> str:
    """Return only the user-friendly text. Debug info is logged to backend logs.

    This creates a clear separation of channels:
    - frontend_response: clean, empathetic text for the user (return value)
    - backend_log: internal details (plan, kritik/critic, meta) written to logs only
    """
    try:
        d = debug or {}
        plan_b = d.get("plan")
        critic_b = d.get("critic") if d.get("critic") is not None else d.get("kritik")
        extra = {k: v for k, v in d.items() if k not in {"plan", "critic", "kritik"}}
        if plan_b or critic_b or extra:
            logger.debug("chat.debug | plan=%s | critic=%s | meta=%s", plan_b, critic_b, extra)
    except Exception:
        # Never break user output because of logging
        pass
    return (message or "").strip()

def _audit_chat(event: Dict[str, Any]) -> None:
    try:
        root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
        logdir = root / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        (logdir / "audit_chat.jsonl").open("a", encoding="utf-8").write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass

def is_question(s: str) -> bool:
    s = (s or "").strip().lower()
    return s.endswith("?") or any(k in s for k in ["was ist", "was weißt", "erkläre", "wieso", "warum", "wie funktioniert"])

def is_uncertain(text: str) -> bool:
    return bool(_UNSURE.search(text or ""))

def _trust_badge(url: str) -> str:
    try:
        h = _source_host(url)
        if not h:
            return "⚪"
        dom = h.lower()
        if "wikipedia.org" in dom or dom.endswith(".gov") or ".gov." in dom or dom.endswith(".edu") or ".edu." in dom or dom.endswith(".ac.uk") or ".ac." in dom:
            return "🟢"
        return "⚪"
    except Exception:
        return "⚪"

def format_sources(sources: List[dict], limit: int = 2) -> str:
    if not sources:
        return ""
    out = []
    for s in sources[:limit]:
        title = s.get("title") or s.get("site") or "Quelle"
        url = s.get("url") or s.get("link") or ""
        badge = _trust_badge(url)
        out.append(f"- {badge} {title} ({url})")
    return "\n\nQuellen:\n" + "\n".join(out)

def _text_has_sources_section(text: str) -> bool:
    try:
        if not text:
            return False
        t = (text or '').lower()
        keys = [
            "quellen:",            # generic German block
            "aktuelle quellen",    # our web sources header
            "sources:",            # English variant
        ]
        return any(k in t for k in keys)
    except Exception:
        return False

def retrieve_context_for_prompt(user_message: str) -> Dict[str, Any]:
    """Return snippet and block IDs from long-term memory to enrich LLM prompts.
    Uses the lightweight inverted index in system/knowledge_access.py.
    """
    try:
        if not _kb_search or not _kb_snippets:
            return {"snippet": "", "ids": []}
        hits = _kb_search(topic=None, tags=None, source=None, text=(user_message or ""), limit=3) or []
        ids = []
        for h in hits:
            if not isinstance(h, dict):
                continue
            bid = h.get("hash") or h.get("id") or ""
            if bid:
                ids.append(str(bid))
        snippet = _kb_snippets(user_message or "", max_chars=1000) if hits else ""
        return {"snippet": (snippet or "").strip(), "ids": ids}
    except Exception:
        return {"snippet": "", "ids": []}

def _source_host(url: str) -> str:
    try:
        import urllib.parse as up
        return up.urlparse(url or "").netloc.lower()
    except Exception:
        return ""

def _filter_sources_by_env(sources: List[dict]) -> List[dict]:
    allowed = os.getenv("KI_WEB_ALLOWED", "").strip()
    if not allowed:
        return sources
    white = {h.strip().lower() for h in allowed.split(',') if h.strip()}
    out = []
    for s in sources or []:
        url = s.get('url') or s.get('link') or ''
        host = _source_host(url)
        if host in white:
            out.append(s)
    return out or sources

def _extract_bullets(text: str, max_items: int = 3) -> List[str]:
    try:
        lines = [l.strip(" -*\t") for l in (text or '').splitlines()]
        items = [l for l in lines if l and not l.lower().startswith(('plan:', 'schritte:', 'steps:', 'todo:'))]
        out = []
        for l in items:
            out.append(l)
            if len(out) >= max_items:
                break
        return out
    except Exception:
        return []

# Prefer unified planner if available
try:
    from ...agent.planner import deliberate_pipeline as _PLN_DELIB  # type: ignore
except Exception:
    _PLN_DELIB = None  # type: ignore

async def deliberate_pipeline(user_msg: str, *, persona: str, lang: str, style: str, bullets: int, logic: str, fmt: str, retrieval_snippet: str = "", retrieval_ids: Optional[List[str]] = None) -> Tuple[str, List[dict], str, str]:
    if _PLN_DELIB is not None:
        try:
            ans, srcs, p, c = _PLN_DELIB(user_msg, persona=persona, lang=lang, style=style, bullets=bullets, logic=logic, fmt=fmt)
            return ans, srcs, p, c
        except Exception:
            pass
    """Planner -> Researcher -> Writer -> Critic -> Refine.
    Returns (final_answer, sources, plan_brief, critic_brief).
    """
    # 1) Planner
    try:
        plan_prompt = (
            "Du bist Planer. Erstelle in 2–4 kurzen Punkten einen Plan, wie du die Frage beantwortest. "
            "Nenne dabei 1–3 Teilfragen oder Stichwörter, die recherchiert werden sollten. "
            "Nur die stichpunktartige Liste, keine Prosa.\n\nFrage:\n" + user_msg
        )
        plan = await call_llm_once(plan_prompt, system_prompt(persona), lang, persona)
    except Exception:
        plan = "- Kurz antworten\n- 1–2 Quellen prüfen"
    plan_items = _extract_bullets(plan, max_items=3)

    # 2) Researcher
    srcs: List[dict] = []
    notes: List[str] = []
    queries = plan_items[:2] if plan_items else []
    if not queries:
        queries = [user_msg]
    for q in queries:
        ans, s = try_web_answer(q, limit=3)
        if ans:
            notes.append(ans.strip())
        for it in (s or []):
            if it and (it.get('url') or it.get('title')):
                srcs.append(it)

    # 3) Writer
    try:
        research_text = ("\n\n".join(notes)).strip()
        writer_prompt = (
            "Du bist Schreiber. Verfasse eine hilfreiche, prägnante Antwort basierend auf den Notizen. "
            "Halte dich an {style} und die gewünschte Struktur ({fmt}). Antworte auf {lang}. "
            "Gib NUR die Antwort aus, keine Prosa.\n\nNotizen:\n" + (research_text or "(keine)")
        ).format(style=style, fmt=fmt, lang=lang)
        # Inject retrieval context before the actual prompt if available
        if (retrieval_snippet or "").strip():
            prefix = "[Kontextwissen]:\n" + retrieval_snippet.strip() + "\n\n[Nutzerfrage]:\n" + (user_msg or "").strip() + "\n\n"
            writer_prompt = prefix + writer_prompt
        draft = await call_llm_once(writer_prompt, system_prompt(persona), lang, persona)
    except Exception:
        draft = ""

    # 4) Critic
    try:
        critic_prompt = (
            "Du bist Kritiker. Prüfe die folgende Antwort auf Lücken, Unklarheiten, Fehlschlüsse oder fehlende Hinweise. "
            "Gib 2–4 kurze Verbesserungsvorschläge als Liste aus.\n\nAntwort:\n" + (draft or "")
        )
        critic = await call_llm_once(critic_prompt, system_prompt(persona), lang, persona)
    except Exception:
        critic = ""
    critic_items = _extract_bullets(critic, max_items=3)

    # 5) Refine
    final_answer = draft
    if critic_items:
        try:
            refine_prompt = (
                "Überarbeite die Antwort gemäß den folgenden Kritikpunkten. "
                "Ziel: Korrektheit, Klarheit, Ergänzung wichtiger Punkte. "
                "Gib NUR die verbesserte Antwort aus.\n\nAntwort:\n{a}\n\nKritik:\n- {k}\n"
            ).format(a=draft, k="\n- ".join(critic_items))
            improved = await call_llm_once(refine_prompt, system_prompt(persona), lang, persona)
            if improved and isinstance(improved, str) and improved.strip():
                final_answer = improved.strip()
        except Exception:
            pass

    # Compact plan/critic briefs
    plan_brief = "; ".join(plan_items[:2])
    critic_brief = "; ".join(critic_items[:2])
    return final_answer or draft or "", srcs, plan_brief, critic_brief

# -------- Follow‑up helpers -------------------------------------------------
FOLLOWUP_HINTS = {
    "grundlagen", "basics", "einführung", "einfuehrung", "überblick", "ueberblick",
    "übersicht", "uebersicht", "arten", "angriffe", "schutz", "beispiele",
}

def _combine_with_context(sid: str, user_msg: str, extracted_topic: str) -> Tuple[str, str]:
    """If the user sends a short follow‑up like "Grundlagen", combine it with the
    last topic from the session context to avoid drifting to unrelated Wikipedia
    topics. Returns (query, topic_used)."""
    try:
        base = (get_offer_context(sid) or {}).get("topic") or extracted_topic or ""
        msg = (user_msg or "").strip()
        tokens = msg.lower().strip()
        wc = len(tokens.split())
        if base and (tokens in FOLLOWUP_HINTS or wc <= 3):
            return (f"{base} {msg}", base)
        return (user_msg, extracted_topic or base)
    except Exception:
        return (user_msg, extracted_topic)

def memory_bullets(mem_hits: List[dict], limit: int = 3) -> str:
    if not mem_hits:
        return ""
    # Filter triviale/rauschende Titel und dedupliziere per Titel
    seen = set()
    lines = []
    # Prefer web-sourced items first
    def _prio(m: dict) -> int:
        tags = m.get('tags') or []
        meta = m.get('meta') or {}
        if isinstance(tags, list) and 'web' in tags:
            return 0
        if isinstance(meta, dict) and str(meta.get('source','')).lower() in {'web','web_enrich'}:
            return 0
        return 1
    sorted_hits = sorted(mem_hits, key=_prio)
    GREET_RX = re.compile(r"^(hallo|hey|hi|servus|gr[üu]ss?\s*dich)\b", re.I)
    BAD_TITLE_RX = re.compile(r"^(was\s+wei?sst?\b|wie\s+geht|gute\s+frage)\b", re.I)
    BAD_CONTENT_RX = re.compile(r"^(gute\s+frage!|\(relevante\s+notizen\))", re.I)
    count = 0
    for m in sorted_hits:
        title = (m.get('title') or '').strip()
        tl = title.lower()
        if not title:
            continue
        if tl in seen:
            continue
        # Filter out generic digests and salutations
        if tl.startswith('web digest') or GREET_RX.search(title) or BAD_TITLE_RX.search(title):
            continue
        content = (m.get('content') or '').strip()
        meta = m.get('meta') or {}
        # Skip low-information auto-learned chat echoes
        if isinstance(meta, dict) and str(meta.get('source','')).lower() == 'chat' and BAD_CONTENT_RX.search(content):
            continue
        seen.add(tl)
        snippet = content.replace('\n', ' ')[:180].strip()
        if not snippet:
            continue
        lines.append(f"• {title}: {snippet}")
        count += 1
        if count >= max(1, int(limit or 3)):
            break
    if not lines:
        return ""
    return "\n\n(Relevante Notizen)\n" + "\n".join(lines)

def render_choice(choice: str, topic: str) -> str:
    if choice == "kurz":
        return f"Soll ich {topic} in 2–3 Sätzen kurz erklären?"
    if choice == "zusammenfassung":
        return f"Möchtest du eine knappe Zusammenfassung zu {topic} in Stichpunkten?"
    if choice == "plan":
        return f"Soll ich dir zu {topic} einen kleinen Fahrplan mit 3–4 Schritten vorschlagen?"
    return "Was hättest du lieber: kurz erklärt, Stichpunkte oder ein kleiner Plan?"

async def execute_choice(choice: str, topic: str, user: str, persona: str, lang: str) -> str:
    """Execute an explicit user choice. Prefer local LLM; otherwise, synthesize
    a compact answer from web + memory without prompt‑echoing.
    """
    # Try local LLM info via netapi.brain.llm_local
    has_llm = False
    try:
        from ..brain import llm_local as _llm  # type: ignore
        has_llm = bool(getattr(_llm, 'available', lambda: False)())
    except Exception:
        has_llm = False

    if has_llm:
        instr = {
            "kurz": f"Erkläre {topic or 'das Thema'} in 2–3 Sätzen, direkt & präzise.",
            "zusammenfassung": f"Fasse {topic or 'das Thema'} in 4–6 Stichpunkten zusammen.",
            "plan": (
                f"Erstelle einen 25-Minuten-Lernplan zu {topic or 'dem Thema'}:\n"
                "1) Grundlagen (5)\n2) Kernkonzepte (10)\n3) Anwendungen (8)\n4) Quellen (2)"
            ),
        }.get(choice, f"Erkläre {topic or 'das Thema'} kurz.")
        sys = system_prompt(persona)
        prompt = f"{instr}\n\nFrage des Nutzers: {user}"
        return await call_llm_once(prompt, sys, lang, persona)

    # No local LLM → synthesize from web + memory
    t = topic or user
    ans, sources = try_web_answer(t, limit=4)
    # collect memory
    mh = recall_mem(t, top_k=3) or []
    mh = [m for m in mh if float(m.get('score',0)) >= MEM_MIN_SCORE][:3]
    if mh:
        mh = _filter_hits_by_topic(mh, topic)
    note = memory_bullets(mh)

    if choice == 'plan':
        steps = [
            f"1) Überblick: {short_summary(ans or '', max_chars=160) or (topic or 'Thema')}",
            "2) Kernbegriffe in 5 Stichpunkten", 
            "3) Zwei Beispiele aus der Praxis",
            "4) 2 Quellen prüfen/merken"
        ]
        out = f"Mini‑Plan zu {topic or 'dem Thema'}:\n" + "\n".join(f"- {s}" for s in steps)
    elif choice == 'zusammenfassung':
        parts = []
        if ans:
            parts.append(ans.strip())
        if note:
            parts.append(note.strip())
        out = "\n\n".join(p for p in parts if p) or _fallback_reply(user)
    else:  # 'kurz' or default
        text = ans or (mh[0].get('content') if mh else '') or ''
        out = short_summary(text, max_chars=320) if text else _fallback_reply(user)
        if note:
            out = (out + "\n\n" + note).strip()
    if ans and sources:
        src_block = format_sources(sources, limit=2)
        if src_block:
            out += "\n\n" + src_block
    return clean(out)

# -------------------------------------------------
# Brain/LLM Aufrufe (weich)
# -------------------------------------------------
async def call_llm_once(user: str, system: str, lang: str = "de-DE", persona: str = "friendly") -> str:
    try:
        if _has_brain_sync():
            from ..brain import respond_to  # type: ignore
            return respond_to(user, system=system, lang=lang, persona=persona)
    except Exception:
        pass
    try:
        from ...core.dialog import respond_to  # type: ignore
        return respond_to(user, system=system, lang=lang, persona=persona)
    except Exception:
        pass
    return _fallback_reply(user)

async def stream_llm(user: str, system: str, lang: str = "de-DE", persona: str = "friendly") -> AsyncGenerator[str, None]:
    """Unified LLM streaming with diagnostics and safe fallbacks.

    Features:
    - Logs start and selected branch
    - Optional dummy mode via env KI_STREAM_DUMMY=1
    - First-chunk timeout to prevent hanging streams
    - Falls back to one-shot answer if streaming not available
    """
    try:
        logger.info("stream_llm: start (persona=%s, lang=%s)", persona, lang)
    except Exception:
        pass

    # 0) Dummy mode for testing end-to-end streaming without LLM
    try:
        if os.getenv("KI_STREAM_DUMMY", "0").strip() in {"1", "true", "True"}:
            logger.info("stream_llm: KI_STREAM_DUMMY enabled – emitting test chunks")
            yield "Hallo von KI_ana"
            await asyncio.sleep(0.05)
            yield " – Test erfolgreich"
            return
    except Exception:
        pass

    async def _yield_with_first_timeout(gen, *, first_timeout: float = 2.5) -> AsyncGenerator[str, None]:
        """Yield from an async generator but guard the first chunk with a timeout.
        If the first chunk doesn't arrive in time, raise TimeoutError to allow fallback.
        """
        got_first = False
        try:
            first = await asyncio.wait_for(gen.__anext__(), timeout=first_timeout)
            got_first = True
            yield first
        except asyncio.TimeoutError:
            try:
                logger.warning("stream_llm: first chunk timed out after %.2fs", first_timeout)
            except Exception:
                pass
            raise
        except StopAsyncIteration:
            return
        # Drain the rest without a strict timeout
        if got_first:
            try:
                while True:
                    nxt = await gen.__anext__()
                    yield nxt
            except StopAsyncIteration:
                return

    # 1) Prefer internal brain streaming if available
    try:
        if _has_brain_stream():
            try:
                logger.info("stream_llm: using ..brain.stream_response")
            except Exception:
                pass
            from ..brain import stream_response  # type: ignore
            agen = stream_response(user, system=system, lang=lang, persona=persona)
            try:
                async for chunk in _yield_with_first_timeout(agen):
                    yield chunk
                return
            except asyncio.TimeoutError:
                # Fall through to next provider
                try:
                    logger.info("stream_llm: ..brain.stream_response timed out; falling back")
                except Exception:
                    pass
    except Exception as e:
        try:
            logger.exception("stream_llm: brain stream failed: %s", e)
        except Exception:
            pass

    # 2) Try core.dialog streaming if available
    try:
        try:
            logger.info("stream_llm: using core.dialog.stream_response")
        except Exception:
            pass
        from ...core.dialog import stream_response  # type: ignore
        agen2 = stream_response(user, user_context={"lang": lang}, system=system, lang=lang, persona=persona)
        try:
            async for chunk in _yield_with_first_timeout(agen2):
                yield chunk
            return
        except asyncio.TimeoutError:
            try:
                logger.info("stream_llm: core.dialog.stream_response timed out; falling back to one-shot")
            except Exception:
                pass
    except Exception as e:
        try:
            logger.exception("stream_llm: core.dialog stream failed: %s", e)
        except Exception:
            pass

    # 3) Fallback: einmalige Antwort emittieren
    try:
        logger.info("stream_llm: using one-shot fallback call_llm_once")
    except Exception:
        pass
    yield await call_llm_once(user, system, lang, persona)


def _fallback_reply(user: str) -> str:
    u = (user or "").strip()
    ul = u.lower()
    # 1) Gruß priorisieren (verhindert Fehlklassifikation von "Wie geht's?")
    if _HOW_ARE_YOU.search(ul):
        return "Mir geht’s gut, danke! 😊 Wie geht’s dir – und wobei kann ich helfen?"
    if _GREETING.search(ul):
        return "Hallo! 👋 Wie kann ich dir helfen?"
    # 2) Frage behandeln
    if _DEF_Q_RX.search(u) or any(k in ul for k in ["was ist", "was weißt", "wieso", "warum", "wie funktioniert"]):
        return "Hier ist eine kurze Antwort. Wenn du willst, gehe ich danach gern tiefer oder auf Bereiche ein, die dich besonders interessieren."
    # 3) Lernintent
    if "lern" in ul or "lernen" in ul:
        m = re.search(r"über\s+([a-z0-9äöüß \-]+)", ul)
        topic = (m.group(1).strip().title() if m else "das Thema")
        return f"Klar, ich kann {topic} lernen. Ich gebe dir erst eine kurze Antwort und kann dann weiter vertiefen – sag einfach, wohin."
    return "Alles klar 🙂 – worum genau geht’s dir dabei?"

# -------------------------------------------------
# Web-Antwort / Suche
# -------------------------------------------------

def try_web_answer(q: str, limit: int = 5) -> Tuple[Optional[str], List[dict]]:
    """Portable Web-Antwort basierend auf web_qa.web_search_and_summarize.

    Gibt (answer_text, sources) zurück. answer_text ist eine kompakte
    Zusammenfassung der Top-Resultate, sources enthält [{title,url},...].
    """
    try:
        from ... import web_qa  # lazy import
    except Exception:
        # If web_qa is not available, signal no web answer
        return None, []

    # Use web_qa when available and always return a tuple
    try:
        res = web_qa.web_search_and_summarize(q, user_context={"lang": "de"}, max_results=limit)
        if not res or not res.get("allowed"):
            return None, []
        items = res.get("results") or []
        # Apply policy filter (allowlist) if configured
        items = _filter_sources_by_env(items)
        if not items:
            return None, []
        # Build compact answer text from the first 1-2 results
        lines: List[str] = []
        sources: List[dict] = []
        for it in items[:2]:
            title = it.get("title") or "Quelle"
            summary = (it.get("summary") or "").strip()
            url = it.get("url") or ""
            if summary:
                lines.append(f"{summary}")
            sources.append({"title": title, "url": url})
        text = "\n\n".join(lines).strip()
        return (text or None), sources
    except Exception:
        return None, []

def _force_web_answer(q: str, limit: int = 3) -> Tuple[Optional[str], List[dict]]:
    """Minimaler Web‑Fallback, auch wenn globales Netz deaktiviert ist.
    Nutzt Wikipedia OpenSearch + Seitenabruf und baut eine kurze Antwort.
    """
    try:
        import requests
        from bs4 import BeautifulSoup  # type: ignore
        lang = "de"
        base = f"https://{lang}.wikipedia.org/w/api.php"
        r = requests.get(base, params={"action":"opensearch","format":"json","search":q,"limit":limit}, timeout=10)
        items = []
        if r.ok:
            data = r.json()
            titles = data[1] if isinstance(data, list) and len(data)>=2 else []
            links  = data[3] if isinstance(data, list) and len(data)>=4 else []
            for t,u in list(zip(titles, links))[:limit]:
                items.append({"title": t, "url": u})
        sources = []
        paras = []
        for it in items[:2]:
            url = it.get("url") or ""
            if not url:
                continue
            rr = requests.get(url, timeout=10, headers={"User-Agent":"KI_ana/force-web"})
            if not rr.ok:
                continue
            soup = BeautifulSoup(rr.text, "html.parser")
            for bad in soup(["script","style","noscript","header","footer","nav","form","aside"]):
                bad.extract()
            ps = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
            ps = [p for p in ps if len(p) > 60]
            if ps:
                paras.extend(ps[:2])
                sources.append({"title": it.get("title") or "Wikipedia", "url": url})
        if not paras:
            return None, []
        bullets = [p[:220] + ("…" if len(p)>220 else "") for p in paras[:5]]
        body = "Wesentliches:\n" + "\n".join("• "+b for b in bullets)
        tldr = "\n\nKurz gesagt: " + bullets[0]
        return (body + tldr).strip(), sources
    except Exception:
        return None, []

    try:
        res = web_qa.web_search_and_summarize(q, user_context={"lang": "de"}, max_results=limit)
        if not res or not res.get("allowed"):
            return None, []
        items = res.get("results") or []
        # Apply policy filter (allowlist) if configured
        items = _filter_sources_by_env(items)
        if not items:
            return None, []
        # Baue kompakten Antworttext aus den ersten 1-2 Treffern
        lines = []
        sources = []
        for it in items[:2]:
            title = it.get("title") or "Quelle"
            summary = (it.get("summary") or "").strip()
            url = it.get("url") or ""
            if summary:
                lines.append(f"{summary}")
            sources.append({"title": title, "url": url})
        text = "\n\n".join(lines).strip()
        return (text or None), sources
    except Exception:
        return None, []

def _filter_hits_by_topic(mem_hits: List[dict], topic: str) -> List[dict]:
    """Prefer memory hits that actually mention the topic to reduce noise.
    If no filtered hits remain, return the original list.
    """
    try:
        t = (topic or "").strip().lower()
        if not t or len(t) < 3:
            return mem_hits
        keep = []
        for m in mem_hits:
            title = str((m.get('title') or '')).lower()
            content = str((m.get('content') or '')).lower()
            if t in title or t in content:
                keep.append(m)
        return keep or mem_hits
    except Exception:
        return mem_hits


def _coerce_to_dict(raw: Any) -> dict:
    try:
        from pathlib import Path as _Path
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, (list, tuple)):
            return _coerce_to_dict(raw[0]) if raw else {}
        if isinstance(raw, (str, _Path)):
            return {"file": str(raw)}
        return {}
    except Exception:
        return {}

def save_memory(title: str, content: str, tags: List[str], url: Optional[str] = None, *, chain_hint: bool = False) -> dict:
    """Persist via memory_store and always return a normalized dict with id, file, url, tags."""
    try:
        from ... import memory_store as _mem  # lazy import (netapi/memory_store.py)
        # Build normalized tags once
        try:
            tags_norm = list(set((list(tags or [])) + ["vision"]))
        except Exception:
            tags_norm = ["vision"]

        # Normalize/repair title: avoid saving confirmation phrases as title
        try:
            t_in = str(title or "").strip()
            low = t_in.lower()
            confirm_keys = {"ja, speichern", "ja speichern", "speichere", "bitte speichern", "speichern"}
            title_final = t_in
            if not t_in or low in confirm_keys:
                # Try to derive topic from content (e.g., "Kurzüberblick zu Mars ...")
                import re as _re
                t_guess = ""
                try:
                    m = _re.search(r"Kurzüberblick\s+zu\s+([^\n\r:]+)", str(content or ""), flags=_re.IGNORECASE)
                    if m:
                        t_guess = m.group(1).strip()
                except Exception:
                    t_guess = ""
                # If guess is a confirmation phrase or empty, try to derive from URL
                try:
                    if not t_guess or t_guess.lower() in confirm_keys:
                        from urllib.parse import urlparse, unquote
                        u = str(url or "").strip()
                        if u:
                            path = urlparse(u).path or ""
                            seg = (path.strip("/").split("/")[-1] if path else "")
                            if seg:
                                # Strip common wiki patterns like "Mars_(Planet)"
                                seg = unquote(seg)
                                seg = seg.replace("_", " ")
                                # Prefer inside parentheses if present
                                pm = _re.search(r"^(.+?)\s*\((.+)\)$", seg)
                                if pm:
                                    # e.g., "Mars (Planet)" -> "Mars"
                                    t_guess = pm.group(1).strip()
                                else:
                                    t_guess = seg.strip()
                except Exception:
                    pass
                if not t_guess:
                    try:
                        # Fallback to extractor if available in this module
                        t_guess = (extract_topic(str(content or "")) or "").strip()
                    except Exception:
                        t_guess = ""
                title_final = (t_guess or t_in or "").strip()[:120]
        except Exception:
            title_final = (str(title or "").strip() or "")[:120]

        # Call store (new API preferred)
        raw: Any = {}
        if hasattr(_mem, "save_memory_entry"):
            raw = _mem.save_memory_entry(title=title_final, content=content, tags=tags_norm, url=url)
        elif hasattr(_mem, "add_block"):
            bid = _mem.add_block(title=title_final, content=content, tags=tags_norm, url=url, meta={"source": "chat", "chain_hint": bool(chain_hint)})
            raw = {"file": f"{bid}.json", "id": bid, "url": url or ""} if isinstance(bid, str) and bid else {}
        else:
            raw = {}

        # Debug raw type/value
        if os.environ.get("KI_DEBUG_SAVE") == "1":
            try:
                logger.info("[KI_DEBUG_SAVE] save_memory raw type=%s value=%s", type(raw), raw)
            except Exception:
                pass

        # Coerce and normalize
        res = _coerce_to_dict(raw)
        # If empty or malformed, build guaranteed clean fallback
        if not isinstance(res, dict) or not res or not (res.get("id") or res.get("file") or res.get("url")):
            res = {
                "id": f"BLK_auto_{int(time.time())}",
                "file": "",
                "url": str(url or ""),
                "tags": ["vision"],
            }
        # URL precedence: passed url wins over stored
        res["url"] = str((url if url is not None else res.get("url")) or "")
        try:
            res_tags = sorted(set((list(res.get("tags") or [])) + (list(tags or [])) + ["vision"]))
        except Exception:
            res_tags = ["vision"]
        res["tags"] = res_tags

        bid = _extract_block_id(res) or f"BLK_auto_{int(time.time())}"
        res["id"] = str(bid)
        # Ensure file
        f = str(res.get("file") or res.get("path") or res.get("block_file") or "").strip()
        if not f:
            res["file"] = f"{res['id']}.json"
        else:
            try:
                from pathlib import Path as _Path
                res["file"] = f"{_Path(f).stem}.json"
            except Exception:
                res["file"] = f"{res['id']}.json"

        # Debug normalized (and via helper for consistency)
        if os.environ.get("KI_DEBUG_SAVE") == "1":
            try:
                logger.info("[KI_DEBUG_SAVE] save_memory_wrap: bid=%s blk=%s", res.get("id"), res)
            except Exception:
                pass
            try:
                _debug_save("save_memory_wrap", res)
            except Exception:
                pass

        return res
    except Exception as e:
        try:
            logger.error("save_memory_entry failed: %s", e)
        except Exception:
            pass
        return {"id": f"BLK_auto_{int(time.time())}", "file": "", "url": url or "", "tags": ["vision"]}

# -------------------------------------------------
# Knowledge Address Book (Papa-Modus)
# -------------------------------------------------

@router.get("/addressbook")
async def get_address_book(
    q: Optional[str] = None,
    current=Depends(get_current_user_opt),
):
    """
    Papa-Modus: Liefert das Wissens-Adressbuch (Blockchain-/Memory-Blöcke) als Liste.
    Quelle ist ADDRBOOK_PATH (JSON), gepflegt beim Speichern/Lernen.
    """
    # Guard: erlauben wenn Papa‑Modus aktiv ODER aktueller User admin ist
    papa_on = os.getenv("PAPA_MODE", "").lower() in {"1", "true", "on"}
    is_admin = _has_any_role(current, {"admin"})
    if not papa_on and not is_admin:
        raise HTTPException(status_code=403, detail="Papa-Modus ist nicht aktiviert (nur Admin)")

    # Best-effort Migration auf neues Schema
    try:
        migrate_addressbook_schema()
    except Exception:
        pass

    # addressbook.json Schema:
    # {
    #   "blocks": [
    #     {"topic":"Geschichte","block_id":"abcd1234","path":"/chain/blocks/.../history_ww2.json",
    #      "source":"Wikipedia","timestamp":"2025-09-06T18:23:00","rating":0.8}
    #   ]
    # }
    data_raw: Any = {"blocks": []}
    try:
        if ADDRBOOK_PATH.exists():
            data_raw = json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8")) or {"blocks": []}
    except Exception:
        data_raw = {"blocks": []}

    # Support both schemas: {"blocks": [...]} and legacy {topic: {block_file,url,updated_at}}
    blocks: List[Dict[str, Any]] = []
    if isinstance(data_raw, dict) and isinstance(data_raw.get("blocks"), list):
        blocks = data_raw.get("blocks") or []
    elif isinstance(data_raw, dict):
        # legacy mapping -> normalize to blocks list
        for topic, entry in (data_raw or {}).items():
            try:
                path = (entry.get("path") or entry.get("block_file") or "")
                if path and "/" not in path:
                    path = f"memory/long_term/blocks/{path}"
                block_id = ""
                if path:
                    try:
                        block_id = Path(str(path)).stem
                    except Exception:
                        pass
                blocks.append({
                    "topic": topic,
                    "block_id": block_id,
                    "path": path,
                    "source": entry.get("source") or entry.get("url") or "",
                    "timestamp": entry.get("timestamp") or entry.get("updated_at") or None,
                    "rating": entry.get("rating") or 0,
                })
            except Exception:
                continue
    else:
        blocks = []

    # Optionales Filter nach Query
    if q:
        ql = q.lower().strip()
        def _match(b: dict) -> bool:
            return any(
                ql in str(b.get(k, "")).lower()
                for k in ("topic", "path", "source", "block_id")
            )
        blocks = [b for b in blocks if _match(b)]

    # Vertrauens-Rating aus Memory-Index anreichern (falls vorhanden)
    try:
        from ... import memory_store as _mem  # type: ignore
        def _host_score(u: str) -> float:
            try:
                import urllib.parse as up
                host = up.urlparse(u or "").netloc.lower()
                good = ("wikipedia", ".gov", ".edu", "nature.com", "nih.gov", "who.int")
                if any(g in host for g in good):
                    return 0.9
                if host:
                    return 0.6
                return 0.5
            except Exception:
                return 0.5
        def _trust_from(b: dict, rating_avg: float) -> dict:
            try:
                src = str(b.get("source") or "")
                t_src = _host_score(src)
                # Age factor (simple): newer entries slightly higher (if integer ts)
                try:
                    ts = b.get("timestamp")
                    if isinstance(ts, str) and ts.isdigit():
                        ts = int(ts)
                    age_s = 0.8
                    if isinstance(ts, (int, float)):
                        import time as _t
                        now = int(_t.time())
                        age = max(0, now - int(ts))
                        two_years = 2*365*24*3600
                        age_s = 1.0 - 0.4 * min(1.0, age / two_years)
                    # Placeholder consistency until deeper cross‑check in place
                    cons = 0.6
                    score = round(0.5*rating_avg + 0.3*t_src + 0.15*age_s + 0.05*cons, 3)
                    return {"score": score, "signals": {"rating": rating_avg, "source": t_src, "age": round(age_s, 3), "consistency": cons}}
                except Exception:
                    pass
            except Exception:
                pass
            return {"score": round(rating_avg, 3), "signals": {"rating": rating_avg}}
        for b in blocks:
            try:
                rid = str(b.get("block_id") or "") or Path(str(b.get("path") or "")).stem
                if not rid:
                    continue
                r = _mem.get_rating(rid)
                if isinstance(r, dict) and "avg" in r:
                    avg = float(r.get("avg") or 0.0)
                    b["rating"] = avg
                    # optional trust field
                    b["trust"] = _trust_from(b, avg)
                    try:
                        cnt = int(r.get("count") or 0)
                        b["rating_count"] = cnt
                    except Exception:
                        pass
            except Exception:
                continue
    except Exception:
        pass

    return {"ok": True, "blocks": blocks}

@router.post("")
async def chat_once(body: ChatIn, request: Request, db=Depends(get_db), current=Depends(get_current_user_opt)):
    user_msg = (body.message or "").strip()
    sid = session_id(request)
    # Gentle risk detection (audit-only)
    risk_flag = False
    try:
        if _is_risky_prompt(user_msg):
            risk_flag = True
            _audit_risky_prompt(current, sid, user_msg)
    except Exception:
        risk_flag = False
    m = CMD_RX.match(user_msg)
    if m:
        cmd, rest = m.group(1).lower(), (m.group(2) or "").strip()
        # Safety‑Rail: Tool‑Use nur für Creator/Admin
        if not _has_any_role(current, {"creator", "admin"}):
            raise HTTPException(403, "forbidden: tool-use requires creator/admin")
        from ..os import syscalls as sc
        if cmd == "run":
            res = sc.sc_proc_run("creator", rest)
        elif cmd == "read":
            res = sc.sc_fs_read("creator", rest)
        elif cmd == "get":
            res = sc.sc_web_get("creator", rest)
        else:
            res = {"ok": False, "error":"unknown"}
        return {"ok": True, "reply": json.dumps(res, ensure_ascii=False, indent=2)}
    if not user_msg:
        raise HTTPException(400, "empty message")

    # Enforce daily quota for free users (no-op for papa/creator)
    try:
        enforce_quota(current, db)
    except HTTPException:
        # bubble up 429 with JSON detail
        raise

    sid = session_id(request)
    last_topic = _LAST_TOPIC.get(sid, "")

    # Rate limit
    ip = request.client.host if request.client else "?"
    if not _rate_allow(ip, "chat_once", limit=40, per_seconds=60):
        raise HTTPException(429, "rate limit: 40/min")

    # Moderation
    blocked, cleaned_msg, reason = moderate(user_msg, _ethics_level())
    if blocked:
        try:
            _audit_chat({"ts": int(time.time()), "sid": sid, "blocked": True, "reason": reason, "user": user_msg})
        except Exception:
            pass
        return {"ok": True, "reply": "Ich kann dabei nicht helfen. Wenn du willst, nenne ich sichere Alternativen oder Hintergründe.", "backend_log": {"moderation": reason}}
    else:
        user_msg = cleaned_msg

    # Style profile: analyze incoming text and prepare profile for application
    uid_str: Optional[str] = None
    try:
        if current and current.get("id") is not None:
            uid_str = str(int(current["id"]))
    except Exception:
        uid_str = None
    detected = {}
    if style_analyzer and hasattr(style_analyzer, 'analyze_text'):
        try:
            detected = style_analyzer.analyze_text(user_msg, lang=(body.lang or 'de')) or {}
        except Exception:
            detected = {}
    persisted = load_user_profile(uid_str) if uid_str else None
    profile_used = dict(persisted or {})
    profile_used.update({k: v for k, v in (detected or {}).items() if v})
    style_consent_needed = bool(uid_str and not (persisted and isinstance(persisted, dict)))
    style_used_meta = {
        "anrede": profile_used.get("anrede"),
        "formell": profile_used.get("formell"),
        "dialekt": profile_used.get("dialekt"),
        "tonfall": profile_used.get("tonfall"),
    }
    style_prompt = ("Darf ich mir deinen Sprachstil merken, damit ich beim nächsten Mal genauso mit dir reden kann?") if style_consent_needed else None
    # Consent lifecycle: handle previous pending consent
    consent_note = ""
    try:
        pend = _STYLE_PENDING.get(sid)
        if pend:
            low_u = user_msg.lower()
            if is_affirmation(user_msg):
                if uid_str and isinstance(pend.get('profile'), dict):
                    save_user_profile(uid_str, pend['profile'])
                _STYLE_PENDING.pop(sid, None)
                consent_note = "Alles klar – ich merke mir deinen Sprachstil."
            elif NEG_RX.search(low_u):
                _STYLE_PENDING.pop(sid, None)
                consent_note = "Alles klar – ich speichere deinen Stil nicht."
    except Exception:
        pass
    # If we plan to prompt now, mark pending so next turn can confirm
    if style_prompt:
        try:
            _STYLE_PENDING[sid] = {"profile": profile_used}
        except Exception:
            pass

    # Frage-Kontext vormerken (hilft, spätere Kurzform/Bestätigung dem Thema zuzuordnen)
    try:
        if is_question(user_msg):
            t0 = extract_topic(user_msg)
            set_offer_context(sid, topic=(t0 or (user_msg[:80] if user_msg else None)), seed=user_msg)
            if t0:
                _LAST_TOPIC[sid] = t0
    except Exception:
        pass

    # Frühe Behandlung von reinen Grüßen (keine Memory/Web/LLM nötig)
    try:
        low = user_msg.lower()
        if _HOW_ARE_YOU.search(low):
            r = "Mir geht’s gut, danke! 😊 Wie geht’s dir – und womit kann ich helfen?"
            r = _apply_style(r, profile_used)
            if style_prompt:
                r = (r + "\n\n" + style_prompt).strip()
            if consent_note:
                r = (r + "\n\n" + consent_note).strip()
            return {"ok": True, "reply": r, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {}}
        if _GREETING.search(low):
            if last_topic:
                # Avoid repeating plain greeting; continue on last topic with options
                r = f"Hallo! 👋 Sollen wir bei ‘{last_topic}’ weitermachen – oder etwas eingrenzen?"
                r = _apply_style(r, profile_used)
                qrs = [f"Weiter mit {last_topic}", "Beispiele zeigen", "Details vertiefen"]
                if style_prompt:
                    r = (r + "\n\n" + style_prompt).strip()
                return {"ok": True, "reply": r, "quick_replies": qrs, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {}}
            else:
                r = "Hallo! 👋 Wie kann ich dir helfen?"
                r = _apply_style(r, profile_used)
                if style_prompt:
                    r = (r + "\n\n" + style_prompt).strip()
                return {"ok": True, "reply": r, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {}}
        calc = try_calc_or_convert(user_msg)
        if calc:
            r = _apply_style(calc, profile_used)
            if style_prompt:
                r = (r + "\n\n" + style_prompt).strip()
            return {"ok": True, "reply": r, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {}}
    except Exception:
        pass

    # 1) Explizite Wahl?
    choice = pick_choice(user_msg)
    if choice:
        ctx = get_offer_context(sid) or {}
        topic_ctx = ctx.get("topic") or extract_topic(user_msg) or ""
        seed_ctx = ctx.get("seed") or user_msg
        set_last_offer(sid, None)
        set_offer_context(sid, topic=(topic_ctx or None), seed=seed_ctx)
        out = await execute_choice(choice, topic_ctx or "das Thema", seed_ctx, body.persona or "friendly", body.lang or "de-DE")
        r = _apply_style(clean(out), profile_used)
        if style_prompt:
            r = (r + "\n\n" + style_prompt).strip()
        return {"ok": True, "reply": r, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {}}

    # 2) „Ja / bitte“ auf letztes Angebot?
    prev = get_last_offer(sid)
    if prev and is_affirmation(user_msg):
        ctx = get_offer_context(sid) or {}
        topic_ctx = (ctx.get("topic") or extract_topic(user_msg) or "das Thema")
        seed_ctx = ctx.get("seed") or user_msg
        out = await execute_choice(prev, topic_ctx, seed_ctx, body.persona or "friendly", body.lang or "de-DE")
        set_last_offer(sid, None)  # nach Ausführung leeren
        r = _apply_style(clean(out), profile_used)
        if style_prompt:
            r = (r + "\n\n" + style_prompt).strip()
        return {"ok": True, "reply": r, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {}}

    # DEFAULT: Unified planner pipeline (Standardpfad) – mit kurzer Timeout & Fallback
    try:
        # Retrieve long-term memory context for this prompt
        _retr = retrieve_context_for_prompt(user_msg)
        _retr_snip = (_retr.get("snippet") or "").strip()
        _retr_ids  = list(_retr.get("ids") or [])
        if _retr_ids:
            _audit_chat({"type": "retrieval_used", "ids": _retr_ids, "q": user_msg})
        async def _run_planner():
            return await deliberate_pipeline(
                user_msg,
                persona=(body.persona or "friendly"), lang=(body.lang or "de-DE"),
                style=_sanitize_style(body.style), bullets=_sanitize_bullets(body.bullets),
                logic=_sanitize_logic(getattr(body, 'logic', 'balanced')),
                fmt=_sanitize_format(getattr(body, 'format', 'structured')),
                retrieval_snippet=_retr_snip, retrieval_ids=_retr_ids,
            )
        ans_pl, srcs_pl, plan_b, critic_b = await asyncio.wait_for(_run_planner(), timeout=PLANNER_TIMEOUT_SECONDS)
        out_text = (ans_pl or "").strip()
        if out_text:
            if _sanitize_format(getattr(body, 'format', 'structured')) == 'structured' or _sanitize_logic(getattr(body,'logic','balanced'))=='strict':
                out_text = build_structured_reply(out_text, [], srcs_pl or [], bullets=_sanitize_bullets(body.bullets), strict=(_sanitize_logic(getattr(body,'logic','balanced'))=='strict'), topic=extract_topic(user_msg))
            src_block = format_sources(srcs_pl or [], limit=3)
            if src_block:
                out_text = (out_text + "\n\n" + src_block).strip()
            autonomy = int(getattr(body, 'autonomy', 0) or 0)
            conv_id = None
            try:
                if current and current.get("id"):
                    uid = int(current["id"])  # type: ignore
                    conv = _ensure_conversation(db, uid, body.conv_id)
                    conv_id = conv.id
                    _save_msg(db, conv.id, "user", user_msg)
                    _save_msg(db, conv.id, "ai", out_text)
                    asyncio.create_task(_retitle_if_needed(conv.id, user_msg, out_text, body.lang or "de-DE"))
            except Exception:
                conv_id = None
            try:
                if autonomy >= 1 and srcs_pl:
                    learned_text = out_text
                    save_memory(title=(extract_topic(user_msg) or user_msg)[:120], content=learned_text, tags=["web","learned"], url=(srcs_pl[0].get('url') if srcs_pl else None))
                elif autonomy >= 2 and out_text and len(out_text)>160 and not srcs_pl:
                    save_memory(title=(extract_topic(user_msg) or user_msg)[:120], content=out_text, tags=["learned"], url=None)
            except Exception:
                pass
            # Prepare backend-only log; do not expose plan/kritik in UI
            backend_log = {"plan": plan_b, "kritik": critic_b, "meta": {"sources_count": len(srcs_pl or []), "pipeline": "planner"}}
            # Planner Pfad: optional Auto‑Modi Signalisierung (leichtgewichtig)
            auto_modes: List[str] = []
            if srcs_pl:
                auto_modes.append('web')
            if plan_b:
                auto_modes.append('chain')
            if critic_b:
                auto_modes.append('critique')
            # Simple role selection stub for Sub‑KIs
            role_used = 'Erklärbär'
            try:
                if srcs_pl and len(srcs_pl) > 0:
                    role_used = 'Forscher'
                elif critic_b:
                    role_used = 'Kritiker'
            except Exception:
                role_used = 'Erklärbär'
            try:
                t_det = extract_topic(user_msg)
                if t_det:
                    _LAST_TOPIC[sid] = t_det
                    # Persist for this conversation if known
                    if conv_id:
                        persist_last_topic(str(conv_id), t_det)
                    else:
                        persist_last_topic(sid, t_det)
            except Exception:
                pass
            # Append retrieval notice if we used long‑term blocks
            if _retr_ids:
                out_text = (out_text + "\n\n" + "📚 Antwort enthält Wissen aus Langzeitgedächtnis: Block-IDs " + ", ".join(_retr_ids)).strip()
            # Ensure we never leak deliberation markers; only return cleaned frontend text
            out_text = format_user_response(out_text, backend_log)
            out_text = _apply_style(out_text, profile_used)
            if style_prompt:
                out_text = (out_text + "\n\n" + style_prompt).strip()
            # persist styled message if possible
            try:
                if conv_id:
                    _save_msg(db, conv_id, "ai", out_text)
            except Exception:
                pass
            if consent_note:
                out_text = (out_text + "\n\n" + consent_note).strip()
            _topic = extract_topic(user_msg)
            quick_replies = _quick_replies_for_topic(_topic, user_msg)
            conv_out = conv_id if conv_id is not None else (body.conv_id or None)
            return {"ok": True, "reply": out_text, "conv_id": conv_out, "auto_modes": auto_modes, "role_used": role_used, "memory_ids": (_retr_ids or []), "quick_replies": quick_replies, "topic": _topic, "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": backend_log}
        # Wenn Planner keine Antwort liefert, falle auf klassische Pipeline zurück
    except asyncio.TimeoutError:
        pass
    except Exception:
        pass

    # 3) Pipeline: Memory -> Web (optional) -> LLM -> Save (Fallback)
    topic = extract_topic(user_msg)
    # Combine follow‑ups with last topic context
    query, topic = _combine_with_context(sid, user_msg, topic)
    mem_hits = recall_mem(query, top_k=3) or []
    mem_hits = [m for m in mem_hits if float(m.get("score", 0)) >= MEM_MIN_SCORE][:3]
    style = _sanitize_style(body.style)
    bullet_limit = _sanitize_bullets(body.bullets)
    logic_mode = _sanitize_logic(getattr(body, 'logic', 'balanced'))
    fmt_mode = _sanitize_format(getattr(body, 'format', 'structured'))
    # reduce noise using extracted topic
    if not mem_hits:
        # Semantic fallback (optional embeddings)
        try:
            from ... import memory_store as _mem  # type: ignore
            sem = _mem.search_blocks_semantic(query, top_k=3, min_score=0.15) or []
            blocks = []
            for bid, sc in sem:
                b = _mem.get_block(bid)
                if b:
                    blocks.append({"id": bid, "title": b.get('title',''), "content": b.get('content',''), "score": float(sc)})
            mem_hits = blocks
        except Exception:
            mem_hits = []
    if mem_hits:
        mem_hits = _filter_hits_by_topic(mem_hits, topic)
        mem_hits = _boost_with_ratings(mem_hits)
    mem_note = memory_bullets(mem_hits, bullet_limit)

    # Web vorziehen, wenn es eine Frage ist oder Memory leer ist
    q_mode = is_question(user_msg)
    need_web = q_mode or (not mem_hits)
    ans, sources = None, []
    learned_text: Optional[str] = None
    learned_url: Optional[str] = None
    block_info: Dict[str, str] = {}

    if need_web:
        try:
            from ...config import settings as _s
            allow_global = bool(getattr(_s, 'ALLOW_NET', True))
        except Exception:
            allow_global = (os.getenv('ALLOW_NET','1')=='1')
        if allow_global:
            ans, sources = try_web_answer(topic or query or user_msg, limit=5)
        elif getattr(body, 'web_ok', False):
            ans, sources = _force_web_answer(topic or query or user_msg, limit=3)

    # Default: Bei Fragen eine kurze Zusammenfassung liefern und danach Nachfragen anbieten
    # Heuristische Auto‑Aktivierung von Modi
    autonomy = int(getattr(body, 'autonomy', 0) or 0)
    ul = user_msg.lower()
    auto_fact = False
    auto_counter = False
    auto_delib = False
    auto_chain = False
    # Chain wenn komplex/mehrteilig oder explizit nach Plan/Schritten gefragt
    if q_mode and (ul.count('?') >= 2 or any(k in ul for k in ['schritte', 'plan', 'vergleich', 'unterschiede', 'pipeline'])):
        auto_chain = True
    # Deliberation bei höherer Autonomie oder längeren Fragen
    if autonomy >= 2 or len(user_msg) > 240:
        auto_delib = False  # konservativ: volle Deliberation nur, wenn explizit gefordert; später ausbaubar
    # Counter bei Pro/Contra oder kontroversen Stichworten
    if any(k in ul for k in ['pro und contra', 'pro/contra', 'gegenargument', 'kritik', 'risiko', 'nachteil', 'ethik', 'privacy', 'datenschutz']):
        auto_counter = True
    # Factcheck wenn keine Quellen, aber eine klare Aussage oder bei strenger Logik
    if (not sources) and (autonomy >= 2 or any(k in ul for k in ['ist wahr', 'stimmt es', 'beweise', 'quelle', 'beleg'])):
        auto_fact = True

    # Kombiniere mit (ggf. noch vorhandenen) manuellen Flags
    flag_counter = bool(getattr(body, 'counter', False) or auto_counter)
    flag_fact = bool(getattr(body, 'factcheck', False) or auto_fact)
    flag_delib = bool(getattr(body, 'deliberation', False) or auto_delib)
    flag_critique = bool(getattr(body, 'critique', False))  # Kritik (Refinement) separat gesteuert

    auto_modes: List[str] = []
    if need_web and sources:
        auto_modes.append('web')
    if auto_chain:
        auto_modes.append('chain')
    if auto_counter:
        auto_modes.append('counter')
    if auto_fact:
        auto_modes.append('factcheck')

    if q_mode:
        # Wenn weder Memory noch Web vorhanden, sag ehrlich Bescheid und versuche Websuche
        if not mem_hits and not ans:
            reply = ("Darüber weiß ich noch nichts – ich schaue kurz im Web nach.\n"
                     "(Falls du willst, kann ich danach mehr ins Detail gehen.)")
            # zweiter Versuch (ggf. Netz war langsam)
            ans2, sources2 = try_web_answer(topic or user_msg, limit=5)
            if ans2:
                # direkte, kompakte Antwort ohne LLM-Zwischenschritt
                reply = (reply + "\n\n" + ans2.strip()).strip()
                src_block = format_sources(sources2, limit=2)
                if src_block:
                    reply += "\n\n" + src_block
                learned_text = ans2.strip(); learned_url = sources2[0].get("url") if (sources2 and sources2[0].get("url")) else None
                block_info = save_memory(title=(topic or user_msg)[:120], content=learned_text, tags=["web","learned"], url=learned_url)
            else:
                reply += "\n\nLeider habe ich dazu aktuell keine verlässlichen Quellen gefunden."
        else:
            # Structured reply (preferred) or simple concatenation
            if fmt_mode == 'structured' or logic_mode == 'strict':
                reply = build_structured_reply(ans or '', mem_hits, sources or [], bullets=bullet_limit, strict=(logic_mode=='strict'), topic=topic)
            else:
                if style == "concise":
                    reply = short_summary((ans or "") + "\n\n" + (mem_note or ""), max_chars=380).strip()
                else:
                    parts = []
                    if ans:
                        parts.append(ans.strip())
                    if mem_note:
                        parts.append(mem_note.strip())
                    reply = "\n\n".join(p for p in parts if p)
            if not reply:
                reply = _fallback_reply(user_msg)
            # Quellen anhängen, falls vorhanden
            if ans:
                src_block = format_sources(sources, limit=2)
                if src_block:
                    reply = (reply + "\n\n" + src_block).strip()
                learned_text = ans.strip(); learned_url = sources[0].get("url") if (sources and sources[0].get("url")) else None
                block_info = save_memory(title=(topic or user_msg)[:120], content=learned_text, tags=["web","learned"], url=learned_url)

        # Gewünschter Stil: zuerst Kurzfassung, dann offene Nachfrage
        if fmt_mode == 'structured' or logic_mode == 'strict':
            # Already structured; keep as is
            reply = reply.strip()
        elif reply and reply.strip():
            reply = ("Kurzfassung:\n\n" + reply.strip())
        reply = (reply + "\n\nMöchtest du mehr? Ich kann vertiefen oder auf bestimmte Bereiche eingehen (z. B. Grundlagen, Arten, Angriffe, Schutz). Sag mir einfach, was dich interessiert.").strip()
        set_last_offer(sid, None); set_offer_context(sid, topic=(topic or user_msg)[:80], seed=user_msg)

        # Optional server-side persistence
        conv_id = None
        try:
            if current and current.get("id"):
                uid = int(current["id"])  # type: ignore
                conv = _ensure_conversation(db, uid, body.conv_id)
                conv_id = conv.id
                _save_msg(db, conv.id, "user", user_msg)
                _save_msg(db, conv.id, "ai", reply)
                asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply, body.lang or "de-DE"))
        except Exception:
            conv_id = None
        reply = _apply_style(reply, profile_used)
        if style_prompt:
            reply = (reply + "\n\n" + style_prompt).strip()
        if consent_note:
            reply = (reply + "\n\n" + consent_note).strip()
        # Backend log channel (empty for this path)
        backend_log = {}
        conv_out = conv_id if conv_id is not None else (body.conv_id or None)
        return {"ok": True, "reply": reply, "conv_id": conv_out, "auto_modes": auto_modes, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": backend_log}

    # Deliberation‑Pipeline (Planner→Researcher→Writer→Critic)
    try:
        if flag_delib:
            final, srcs_d, plan_b, critic_b = await deliberate_pipeline(
                user_msg,
                persona=(body.persona or "friendly"), lang=(body.lang or "de-DE"),
                style=style, bullets=bullet_limit, logic=logic_mode, fmt=fmt_mode
            )
            # Strukturierte Ausgabe optional
            out_text = final.strip()
            if fmt_mode == 'structured' or logic_mode == 'strict':
                out_text = build_structured_reply(out_text, mem_hits or [], srcs_d or [], bullets=bullet_limit, strict=(logic_mode=='strict'), topic=topic)
            # Quellen anhängen
            src_block = format_sources(srcs_d, limit=3)
            if src_block:
                out_text = (out_text + "\n\n" + src_block).strip()
            # Backend-only debug: Plan & Kritik (do not expose in UI)
            debug_info = {"plan": plan_b, "critic": critic_b, "sources_count": len(srcs_d or [])}
            out_text = format_user_response(out_text, debug_info)
            # Persist (optional)
            conv_id = None
            try:
                if current and current.get("id"):
                    uid = int(current["id"])  # type: ignore
                    conv = _ensure_conversation(db, uid, body.conv_id)
                    conv_id = conv.id
                    _save_msg(db, conv.id, "user", user_msg)
                    _save_msg(db, conv.id, "ai", out_text)
                    asyncio.create_task(_retitle_if_needed(conv.id, user_msg, out_text, body.lang or "de-DE"))
            except Exception:
                conv_id = None
            out_text = _apply_style(out_text, profile_used)
            if style_prompt:
                out_text = (out_text + "\n\n" + style_prompt).strip()
            if consent_note:
                out_text = (out_text + "\n\n" + consent_note).strip()
            backend_log = {"plan": plan_b, "critic": critic_b}
            conv_out = conv_id if conv_id is not None else (body.conv_id or None)
            return {"ok": True, "reply": out_text, "conv_id": conv_out, "auto_modes": auto_modes, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": backend_log}
    except Exception:
        pass

    # LLM Input zusammensetzen
    llm_user = user_msg
    if mem_note:
        llm_user += mem_note
    if ans:
        llm_user += "\n\n(Web‑Zusammenfassung)\n" + ans.strip()
    # Anhänge aus der Nachricht annotieren (informativ für das LLM)
    try:
        atts = getattr(body, 'attachments', None)
        if atts:
            lines = ["(Anhänge)"]
            for a in (atts or [])[:5]:
                nm = str(a.get('name') or a.get('url') or 'Datei')
                tp = str(a.get('type') or '')
                url = str(a.get('url') or '')
                lines.append(f"- {nm} ({tp}) {url}")
            llm_user += "\n\n" + "\n".join(lines)
    except Exception:
        pass

    raw = await call_llm_once(
        llm_user,
        system_prompt(body.persona),
        body.lang or "de-DE",
        body.persona or "friendly",
    )
    reply = clean(raw)
    # Bei 'structured' oder 'strict' eine strukturierte Antwort mit Evidenz bauen
    structured = (fmt_mode == 'structured' or logic_mode == 'strict')
    if structured:
        reply = build_structured_reply(ans or '', mem_hits, sources or [], bullets=bullet_limit, strict=(logic_mode=='strict'), topic=topic)
    else:
        if reply:
            reply = "Kurzfassung:\n\n" + reply

    # Optional: Selbstkritik/Refinement in zweiter Pass
    try:
        if flag_critique:
            refine_user = (
                "Überarbeite die folgende Antwort auf die Frage.\n"
                "Ziel: korrigiere Fehler, ergänze wichtige Punkte, verbessere Klarheit.\n"
                "Gib NUR die verbesserte Antwort aus, ohne Analyse.\n\n"
                f"Frage:\n{user_msg}\n\nEntwurf:\n{reply}"
            )
            refined = await call_llm_once(refine_user, system_prompt(body.persona), body.lang or "de-DE", body.persona or "friendly")
            if refined and isinstance(refined, str) and refined.strip():
                reply = clean(refined.strip())
    except Exception:
        pass

    if ans:
        # Quellen beilegen (nur wenn nicht bereits strukturiert eingefügt)
        if not structured:
            reply = (reply + "\n\n" + format_sources(sources, limit=2)).strip()
        learned_text = ans.strip()
        learned_url  = sources[0].get("url") if (sources and sources[0].get("url")) else None
        block_info = save_memory(
            title=(topic or user_msg)[:120],
            content=learned_text,
            tags=["web", "learned"],
            url=learned_url,
        )
    else:
        if mem_hits and (not structured):
            reply = (reply + mem_note).strip()

        # Nur auto-learn, wenn keine Memory‑Notizen angehängt wurden und kein Gruß
        if reply and len(reply) > 120 and "Quellen:" not in reply and not mem_hits and not _GREETING.search(user_msg.lower()):
            learned_text = reply
            block_info = save_memory(
                title=(topic or user_msg)[:120],
                content=learned_text,
                tags=["learned"],
                url=None,
            )

    # Addressbook updaten + Enrichment
    if topic and (block_info.get("file") or learned_url):
        upsert_addressbook(topic, block_file=block_info.get("file", ""), url=learned_url or "")
        enqueue_enrichment(topic)

    # Gegenbeweis: alternative/konträre Quellen ergänzen
    try:
        if flag_counter:
            q_ctr = (f"Kritik an {topic}" if topic else ("Gegenargumente zu " + (query or user_msg)))
            ctr_ans, ctr_sources = try_web_answer(q_ctr, limit=5)
            ctr_sources = _filter_sources_by_env(ctr_sources)
            block = format_sources(ctr_sources, limit=3)
            if ctr_ans:
                reply = (reply + "\n\nGegenposition:\n" + short_summary(ctr_ans, max_chars=320)).strip()
            if block:
                reply = (reply + "\n\nGegenbeweise:" + block.replace("\n\nQuellen:", "")).strip()
    except Exception:
        pass

    # Faktencheck: unabhängig von obiger Web-Phase, ergänze evidenzbasierte Quellen
    try:
        if flag_fact:
            q_fc = topic or query or user_msg
            ans2, sources2 = try_web_answer(q_fc, limit=5)
            src_block = format_sources(sources2, limit=3)
            # Hinweis zu Evidenzstärke
            hint = ""
            if not sources2:
                hint = "\n\nHinweis: Keine belastbare Evidenz gefunden."
            elif len(sources2) == 1:
                hint = "\n\nHinweis: Geringe Evidenz (nur 1 unabhängige Quelle)."
            # Quellen nur anhängen, wenn noch nicht vorhanden
            if "\n\nQuellen:\n" not in reply and src_block:
                reply = (reply + "\n\n" + src_block).strip()
            if hint:
                reply = (reply + hint).strip()
                # Konkrete nächste Schritte vorschlagen (Strict/Factcheck)
                try:
                    if (getattr(body, 'factcheck', False)):
                        steps = [
                            "Relevanz einschränken (Thema/Zeitraum), dann erneut suchen",
                            "2–3 unabhängige, vertrauenswürdige Quellen vergleichen",
                            "Direkte Zitate/Primärquellen prüfen"
                        ]
                        reply = (reply + "\n\nNächste Schritte:\n" + "\n".join(f"- {s}" for s in steps)).strip()
                except Exception:
                    pass
            # Evidenz-ID berechnen (Antwort + URLs)
            urls = " ".join([s.get('url') or '' for s in (sources2 or [])])
            h = hashlib.sha256((reply + "||" + urls).encode('utf-8')).hexdigest()[:10]
            reply = (reply + f"\n\nEvidenz-ID: {h}").strip()
            # Evidence in Memory speichern (Chain‑Hinweis)
            try:
                ev_text = (ans2 or "").strip()
                if src_block:
                    ev_text = (ev_text + "\n\n" + src_block).strip()
                save_memory(
                    title=((topic or user_msg)[:96] + " – Faktencheck"),
                    content=(ev_text or reply[:800]),
                    tags=["evidence", "factcheck", f"evid:{h}"],
                    url=(sources2[0].get('url') if sources2 else None),
                    chain_hint=True,
                )
            except Exception:
                pass
    except Exception:
        pass

    # Kurz-Recap anhängen
    if learned_text:
        reply = (reply + "\n\n(Kurz gelernt)\n" + short_summary(learned_text, max_chars=280)).strip()

    # Abschluss im gewünschten Stil
    reply += "\n\nMöchtest du mehr? Ich kann vertiefen oder auf bestimmte Bereiche eingehen (z. B. Grundlagen, Beispiele, Anwendungen, Schutz)."
    set_last_offer(sid, None)

    try:
        _audit_chat({
            "ts": int(time.time()),
            "sid": sid,
            "persona": body.persona,
            "lang": body.lang,
            "user": user_msg,
            "reply": reply[:4000],
            "topic": topic,
            "learned": bool(learned_text),
        })
    except Exception:
        pass
    # Optional server-side persistence
    conv_id = None
    try:
        if current and current.get("id"):
            uid = int(current["id"])  # type: ignore
            conv = _ensure_conversation(db, uid, body.conv_id)
            conv_id = conv.id
            _save_msg(db, conv.id, "user", user_msg)
            _save_msg(db, conv.id, "ai", reply)
            # Retitle in background
            asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply, body.lang or "de-DE"))
    except Exception:
        conv_id = None
    reply = _apply_style(reply, profile_used)
    if style_prompt:
        reply = (reply + "\n\n" + style_prompt).strip()
    if consent_note:
        reply = (reply + "\n\n" + consent_note).strip()
    conv_out = conv_id if conv_id is not None else (body.conv_id or None)
    return {"ok": True, "reply": reply, "conv_id": conv_out, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {}}

# -------------------------------------------------
# Streaming (SSE)
# -------------------------------------------------
@router.get("/stream")
async def chat_stream(message: str, request: Request, persona: str = "friendly", lang: str = "de-DE", chain: bool = False, conv_id: Optional[int] = None, style: str = "balanced", bullets: int = 5, web_ok: bool = False, autonomy: int = 0):
    user_msg = (message or "").strip()
    # Debug logging at start
    try:
        logger.info("chat_stream: start message=%r persona=%s lang=%s chain=%s conv_id=%s style=%s bullets=%s web_ok=%s autonomy=%s", user_msg, persona, lang, chain, conv_id, style, bullets, web_ok, autonomy)
    except Exception:
        pass
    if not user_msg:
        raise HTTPException(400, "empty message")
    sid = session_id(request)
    # Lightweight correlation id (no extra import): sid + short timestamp suffix
    try:
        _now_ms = int(time.time() * 1000)
    except Exception:
        _now_ms = 0
    cid = f"{sid}:{_now_ms % 1000000:06d}"
    t0 = time.time()
    def _log(level: str, msg: str, *args):
        try:
            pref = f"[cid={cid}] " + msg
            if level == 'info':
                logger.info(pref, *args)
            elif level == 'warning':
                logger.warning(pref, *args)
            elif level == 'error':
                logger.error(pref, *args)
            else:
                logger.debug(pref, *args)
        except Exception:
            pass

    # Helper to construct streaming responses compatible with pytest TestClient
    def _respond(gen):
        """Return EventSourceResponse in normal mode, StreamingResponse in TEST_MODE or when SSE is unavailable."""
        use_test_stream = False
        try:
            use_test_stream = (str(os.getenv("TEST_MODE", "")).strip() in {"1","true","True"})
        except Exception:
            use_test_stream = False
        if (EventSourceResponse is not None) and not use_test_stream:
            try:
                headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
                return EventSourceResponse(gen, ping=15, headers=headers)
            except Exception:
                return EventSourceResponse(gen, ping=15)
        # Wrap dict-yielding generator to raw SSE text for StreamingResponse
        async def _wrap():
            try:
                async for chunk in gen:
                    try:
                        data = ""
                        if isinstance(chunk, dict):
                            data = str(chunk.get("data") or "")
                        else:
                            data = str(chunk)
                        if data:
                            yield ("data: " + data + "\n\n").encode("utf-8")
                    except Exception:
                        continue
                # ensure closing event if generator did not send done
                yield b"data: {\"done\": true}\n\n"
            except Exception:
                yield b"data: {\"done\": true}\n\n"
        return StreamingResponse(_wrap(), media_type="text/event-stream")

    # Basic rate limit per IP
    ip = request.client.host if request.client else "?"
    if not _rate_allow(ip, "chat_stream", limit=40, per_seconds=60):
        # Emit a small SSE error response (or HTTP when SSE off)
        if EventSourceResponse is None:
            raise HTTPException(429, "rate limit: 40/min")
        async def gen_rl():
            # emit cid first for correlation
            yield _sse({"cid": cid})
            yield {"data": json.dumps({"error": "rate_limited", "detail": "Bitte kurz warten (40/min)", "retry": 3000})}
            yield {"data": json.dumps({"done": True})}
        resp = _respond(gen_rl())
        if resp is not None:
            return resp

    # Moderation based on settings
    blocked, cleaned_msg, reason = moderate(user_msg, _ethics_level())
    if blocked:
        # Stream a friendly user-facing note, plus a machine-readable error signal
        if EventSourceResponse is None:
            return {"text": "Ich kann dabei nicht helfen. Wenn du möchtest, kann ich stattdessen sichere Hintergründe erklären.", "done": True}
        async def gen_block():
            out = "Ich kann dabei nicht helfen. Wenn du möchtest, erkläre ich sichere Hintergründe oder Alternativen."
            # User-friendly text (so the preview has content)
            yield _sse({"cid": cid})
            yield {"data": json.dumps({"delta": out})}
            # Error marker for UI logic (finalizes preview on client)
            yield {"data": json.dumps({"error": "moderated", "detail": str(reason or "")[:200], "retry": 0})}
            yield {"data": json.dumps({"done": True})}
        try:
            _audit_chat({"ts": int(time.time()), "sid": sid, "blocked": True, "reason": reason, "user": user_msg})
        except Exception: pass
        resp = _respond(gen_block())
        if resp is not None:
            return resp
    else:
        user_msg = cleaned_msg

    # (Debug SSE bypass removed) – proceed with normal flow

    # Frage-Kontext vormerken
    try:
        if is_question(user_msg):
            _topic0 = extract_topic(user_msg)
            set_offer_context(sid, topic=(_topic0 or (user_msg[:80] if user_msg else None)), seed=user_msg)
    except Exception:
        pass

    topic = extract_topic(user_msg)
    query, topic = _combine_with_context(sid, user_msg, topic)
    mem_hits = recall_mem(query, top_k=3) or []
    mem_hits = [m for m in mem_hits if float(m.get("score", 0)) >= MEM_MIN_SCORE][:3]
    style = _sanitize_style(style)
    bullet_limit = _sanitize_bullets(bullets)

    # 1) Explizite Wahl?
    choice = pick_choice(user_msg)
    if choice:
        ctx0 = get_offer_context(sid) or {}
        topic_ctx0 = ctx0.get("topic") or extract_topic(user_msg) or topic or ""
        seed_ctx0 = ctx0.get("seed") or user_msg
        set_last_offer(sid, None)
        set_offer_context(sid, topic=(topic_ctx0 or None), seed=seed_ctx0)
        async def gen_exec():
            out = await execute_choice(choice, topic_ctx0 or topic or "das Thema", seed_ctx0, persona, lang)
            yield {"data": json.dumps({"delta": clean(out)})}
            yield {"data": json.dumps({"done": True})}
        if EventSourceResponse is None:
            out = await execute_choice(choice, topic_ctx0 or topic or "das Thema", seed_ctx0, persona, lang)
            return {"delta": clean(out), "done": True}
        resp = _respond(gen_exec())
        if resp is not None:
            return resp

    # 2) Bestätigung auf letztes Angebot?
    prev = get_last_offer(sid)
    if prev and is_affirmation(user_msg):
        set_last_offer(sid, None)
        async def gen_prev():
            ctx = get_offer_context(sid) or {}
            topic_ctx = (ctx.get("topic") or topic or "das Thema")
            seed_ctx = ctx.get("seed") or user_msg
            out = await execute_choice(prev, topic_ctx, seed_ctx, persona, lang)
            yield {"data": json.dumps({"delta": clean(out)})}
            yield {"data": json.dumps({"done": True})}
        if EventSourceResponse is None:
            ctx = get_offer_context(sid) or {}
            topic_ctx = (ctx.get("topic") or topic or "das Thema")
            seed_ctx = ctx.get("seed") or user_msg
            out = await execute_choice(prev, topic_ctx, seed_ctx, persona, lang)
            return {"delta": clean(out), "done": True}
        resp = _respond(gen_prev())
        if resp is not None:
            return resp

    # Smalltalk/Gruß vor Planner-Branch abfangen (freundliche Kurzantwort)
    if _HOW_ARE_YOU.search(user_msg.lower()):
        async def gen_smalltalk():
            # Slim, no follow-ups
            yield {"data": json.dumps({"delta": "Mir geht's gut – bereit zu helfen."})}
            yield {"data": json.dumps({"done": True, "no_prompts": True})}
        if EventSourceResponse is None:
            return {"delta": "Mir geht's gut – bereit zu helfen.", "done": True}
        resp = _respond(gen_smalltalk())
        if resp is not None:
            return resp
    if _GREETING.search(user_msg.lower()):
        async def gen_greet():
            yield {"data": json.dumps({"delta": "Hallo! Wie kann ich helfen?"})}
            yield {"data": json.dumps({"done": True, "no_prompts": True})}
        if EventSourceResponse is None:
            return {"delta": "Hallo! Wie kann ich helfen?", "done": True}
        resp = _respond(gen_greet())
        if resp is not None:
            return resp

    # Planner‑Streaming (Standard) – guarded by env flag
    try:
        import os as _os
        _PLANNER_ON = (_os.getenv('KI_PLANNER_ENABLED', '1').strip() in {'1','true','True','yes','on'})
    except Exception:
        _PLANNER_ON = True
    if _PLANNER_ON and (EventSourceResponse is not None):
        # Temporary simplified streaming: use Safety‑Valve to ensure robust, immediate answers
        async def gen_simple():
            try:
                # Emit cid first
                try:
                    yield _sse({"cid": cid})
                except Exception:
                    pass
                # Determine if web is allowed
                web_ok_flag = bool(web_ok)
                try:
                    settings = _read_runtime_settings()
                    if settings:
                        web_ok_flag = web_ok_flag or bool(settings.get("web_ok"))
                except Exception:
                    pass
                # Intent detection for confirmations
                low = (message or "").strip().lower()
                ctx = None
                try:
                    ctx = get_offer_context(sid)
                except Exception:
                    ctx = None
                ctx_topic = (ctx.get("topic") if isinstance(ctx, dict) else None) or (extract_topic(message) or message)
                if any(k in low for k in ["zeige details", "details zeigen", "details"]):
                    # Stream more detailed memory snippets (top 3)
                    try:
                        mem = _kb_snippets(ctx_topic, top_k=3)
                        if mem:
                            def _fmt_ts(ts):
                                try:
                                    t = int(ts)
                                    return time.strftime("%Y-%m-%d", time.gmtime(t))
                                except Exception:
                                    return ""
                            parts = ["📑 Details (Gedächtnis):"]
                            for idx, m in enumerate(mem[:3], start=1):
                                title = (m.get("title") or ctx_topic).strip()
                                cnt = (m.get("content") or "")
                                snip = cnt[:400] + ("…" if len(cnt) > 400 else "")
                                ts = _fmt_ts(m.get("ts"))
                                head = f"🔹 Snippet {idx}: {title}"
                                if ts:
                                    head += f"  ({ts})"
                                parts.append(head)
                                parts.append(snip)
                            out = "\n".join(parts)
                            yield {"data": json.dumps({"delta": out + ("\n" if not out.endswith("\n") else "")})}
                        yield {"data": json.dumps({"done": True, "details": True, "topic": extract_topic(message)})}
                    except Exception:
                        yield {"data": json.dumps({"done": True})}
                    return
                if any(k in low for k in ["ja, vergleiche", "ja vergleiche", "mach den vergleich", "vergleich", "vergleiche"]):
                    # Execute compare flow
                    cmp_txt, cmp_sources = compare_memory_with_web(ctx_topic, web_ok=bool(web_ok_flag))
                    out = (cmp_txt or "")
                    if out:
                        yield {"data": json.dumps({"delta": out + ("\n" if not out.endswith("\n") else "")})}
                    if cmp_sources:
                        block = format_sources_once(out or "", cmp_sources, limit=3)
                        if block:
                            yield {"data": json.dumps({"delta": block})}
                    # Save comparison block (tags include 'comparison') if autonomy >= 2
                    saved_ids: List[str] = []
                    try:
                        if int(autonomy or 0) >= 2 and out:
                            blk = save_memory(
                                title=str(ctx_topic)[:120],
                                content=out,
                                tags=["comparison", "learned"],
                                url=(cmp_sources[0].get("url") if cmp_sources else None),
                            )
                            _debug_save("auto_save_comparison", blk or {})
                            # Memory-save logging
                            try:
                                if blk and isinstance(blk, dict) and blk.get("id"):
                                    logger.info("[memory-save] id=%s source=%s tags=%s", blk.get("id"), blk.get("source"), blk.get("tags"))
                                else:
                                    logger.error("[memory-save] failed for topic=%s", str(ctx_topic)[:120])
                            except Exception:
                                pass

                            try:
                                upsert_addressbook(
                                    ctx_topic or "",
                                    block_file=str((blk or {}).get("file") or ""),
                                    url=(cmp_sources[0].get("url") if cmp_sources else ""),
                                )
                            except Exception:
                                pass

                            bid = ""
                            try:
                                bid = _extract_block_id(blk or {})
                            except Exception as e:
                                logger.error("auto_save_comparison: bad blk type: %s (%s)", type(blk), e)

                            if bid:
                                saved_ids.append(str(bid))
                    except Exception as e:
                        logger.error("auto_save_comparison failed: %s", e, exc_info=True)

                    try:
                        mem_ids = list(saved_ids)
                        # Build finalize payload (sources only from memory here)
                        payload = _finalize_payload("", memory_ids=mem_ids, web_links=[])
                        payload.update({
                            "done": True,
                            "comparison": True,
                            "topic": extract_topic(message),
                        })
                        yield {"data": json.dumps(payload)}
                    except Exception:
                        yield {"data": json.dumps({"done": True})}
                    return
                # Confirmation branch ("ja, speichern") entfernt:
                # KI_ana entscheidet nun selbstständig, ob und wann etwas gespeichert wird.
                # Explizite "ja, speichern"-Eingaben haben keine Sonderbehandlung mehr.
                # Build thoughtful answer using memory check + web compare
                topic_q = extract_topic(message) or message
                a_text, a_origin, a_delta, a_saved_ids, a_sources, a_had_memory, a_had_web, a_mem_count = await answer_with_memory_check(topic_q, web_ok=bool(web_ok_flag), autonomy=int(autonomy or 0))
                txt = (a_text or "").strip()
                srcs = a_sources or []
                if txt:
                    yield {"data": json.dumps({"delta": txt + ("\n" if not txt.endswith("\n") else "")})}
                if srcs:
                    block = format_sources_once(txt or "", srcs, limit=3)
                    if block:
                        yield {"data": json.dumps({"delta": block})}
                # Persist conversation + memory before final meta
                saved_ids: List[str] = []
                try:
                    for _sid in (a_saved_ids or []):
                        if _sid and _sid not in saved_ids:
                            saved_ids.append(str(_sid))
                except Exception:
                    pass
                try:
                    if current and current.get("id"):
                        uid = int(current["id"])  # type: ignore
                        conv = _ensure_conversation(db, uid, conv_id)
                        _save_msg(db, conv.id, "user", message)
                        _save_msg(db, conv.id, "ai", txt)
                        asyncio.create_task(_retitle_if_needed(conv.id, message, txt, lang or "de-DE"))
                except Exception:
                    pass
                # Do not double-save here; answer_with_memory_check already saved when no prior knowledge existed
                # Final meta
                try:
                    mem_ids = list(saved_ids)
                    # include addressbook lookup IDs as context (best-effort)
                    try:
                        for h in (mem_hits or []):
                            bid = h.get('id') or _extract_bid_from_path(str(h.get('path') or ''))
                            if bid:
                                mem_ids.append(str(bid))
                    except Exception:
                        pass
                    # Extract web links from gathered sources (robust: url|link|href) and synthesize if needed
                    from urllib.parse import urlparse as _urlparse
                    import re as _re

                    def _extract_domain(_val: str) -> str:
                        try:
                            s = (str(_val or "")).strip()
                            if not s:
                                return ""
                            if s.startswith(("http://", "https://")):
                                try:
                                    return ( _urlparse(s).netloc or "" ).strip()
                                except Exception:
                                    pass
                            m = _re.search(r"\b([a-z0-9-]+(?:\.[a-z0-9-]+)+)\b", s, _re.I)
                            if m:
                                return m.group(1).lower()
                        except Exception:
                            pass
                        return ""

                    def _collect_web_links_from_sources(_sources: list) -> list[str]:
                        out: list[str] = []
                        try:
                            for _s in (_sources or []):
                                if not isinstance(_s, dict):
                                    continue
                                for _k in ("url", "link", "href"):
                                    _u = _s.get(_k)
                                    if isinstance(_u, str) and _u.strip():
                                        out.append(_u.strip())
                                        break
                        except Exception:
                            pass
                        # de-dup
                        _seen = set(); _uniq = []
                        for _u in out:
                            if _u not in _seen:
                                _seen.add(_u); _uniq.append(_u)
                        return _uniq

                    web_links = _collect_web_links_from_sources(srcs if isinstance(srcs, list) else [])

                    # Synthesize minimal web link if origin suggests web/mixed and allowed but none collected
                    try:
                        _origin_hint = (a_origin or "").strip().lower()
                    except Exception:
                        _origin_hint = "unknown"
                    if (not web_links) and (web_ok_flag in (True, 1, "1", "true", "True")):
                        try:
                            candidates: list[str] = []
                            for _s in (srcs or []):
                                if not isinstance(_s, dict):
                                    continue
                                for _k in ("title", "source", "origin", "provider", "name"):
                                    _v = _s.get(_k)
                                    if isinstance(_v, str) and _v.strip():
                                        candidates.append(_v.strip())
                            if not candidates and isinstance(txt, str) and txt:
                                candidates.append(txt[:120])
                            _domain = ""
                            for _val in candidates:
                                _domain = _extract_domain(_val)
                                if _domain:
                                    break
                            if _domain:
                                web_links = [f"https://{_domain}"]
                        except Exception:
                            web_links = []
                    # No placeholder fallback: if still empty, we will return only memory sources

                    # Build finalize payload with sources
                    payload = _finalize_payload(txt, memory_ids=mem_ids, web_links=web_links)
                    payload.update({
                        "done": True,
                        "safety_valve": True,
                        "origin": (a_origin or "unknown"),
                        "delta_note": (a_delta or ""),
                        "topic": extract_topic(message),
                    })
                    # Finalize source logging
                    try:
                        topic = payload.get("topic") or extract_topic(message)
                        origin = payload.get("origin") or "unknown"
                        logger.info("[chat-finalize] topic=%s origin=%s memory_ids=%s web_links=%s", topic, origin, len(mem_ids or []), len(web_links or []))
                        if origin in ("web", "mixed") and not web_links:
                            logger.warning("[sources] origin=%s but no web links extracted (topic=%s)", origin, topic)
                        if origin == "mixed":
                            found = []
                            if mem_ids: found.append("memory")
                            if web_links: found.append("web")
                            if len(found) < 2:
                                logger.warning("[sources] origin=mixed incomplete (topic=%s, found=%s)", topic, found)
                    except Exception:
                        pass
                    # Perf timing
                    try:
                        elapsed = time.time() - _t0
                        if elapsed > 5.0:
                            logger.warning("[perf] slow answer for topic=%s (%.2fs)", payload.get("topic") or "", elapsed)
                    except Exception:
                        pass
                    try:
                        if a_had_memory and a_had_web:
                            payload["ask_compare"] = True
                        if a_had_memory and int(a_mem_count or 0) >= 2:
                            payload["ask_details"] = True
                    except Exception:
                        pass
                    yield {"data": json.dumps(payload)}
                except Exception:
                    yield {"data": json.dumps({"done": True})}
                return
            except Exception:
                yield _sse_err("stream_failed", "Stream fehlgeschlagen", 1200)
                yield {"data": json.dumps({"done": True})}
        return EventSourceResponse(gen_simple(), ping=15)

# ---- Knowledge helpers: addressbook ↔ memory ↔ web -------------------------
ADDRBOOK_PATH = Path(__file__).resolve().parents[3] / "memory" / "index" / "addressbook.json"
BLOCKS_DIR = Path(__file__).resolve().parents[3] / "memory" / "long_term" / "blocks"

def lookup_addressbook(topic: str) -> List[Dict[str, Any]]:
    try:
        if not ADDRBOOK_PATH.exists():
            return []
        data = _json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8") or "{}")
        blocks = data.get("blocks") or []
        t = (topic or "").strip().lower()
        return [b for b in blocks if str(b.get("topic",""))[:120].strip().lower() == t]
    except Exception:
        return []

def _read_block_json(path: str) -> Dict[str, Any]:
    try:
        p = path or ""
        if p and "/" not in p:
            p = str(BLOCKS_DIR / f"{p}")
        if not p.endswith(".json"):
            p = p + ".json"
        fp = Path(p)
        if not fp.exists():
            return {}
        return _json.loads(fp.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}

def _kb_snippets(topic: str, top_k: int = 5) -> List[Dict[str, Any]]:
    items = lookup_addressbook(topic)
    out: List[Dict[str, Any]] = []
    for it in items[:top_k]:
        blk = _read_block_json(str(it.get("path") or it.get("block_id") or ""))
        if blk:
            out.append({
                "id": blk.get("id") or it.get("block_id"),
                "title": blk.get("title") or topic,
                "content": blk.get("content") or "",
                "url": blk.get("url") or it.get("source") or "",
                "ts": it.get("timestamp") or blk.get("timestamp") or None,
            })
    return out

def _answer_from_web(topic: str, top_k: int = 3) -> (str, List[Dict[str, Any]]):
    try:
        ans, sources = try_web_answer(topic, limit=top_k)
        return (ans or ""), (sources or [])
    except Exception:
        return "", []

def _db_path_from_env() -> str:
    try:
        db_url = os.getenv("DATABASE_URL", "sqlite:///db.sqlite3").strip()
        if db_url.startswith("sqlite:///"):
            return os.path.expanduser(db_url[len("sqlite:///"):])
        if db_url.startswith("sqlite://"):
            return os.path.expanduser(db_url[len("sqlite://"):])
        return os.path.expanduser(db_url)
    except Exception:
        return "db.sqlite3"

def _fetch_memory_snippets(topic: str, limit: int = 3) -> List[Dict[str, Any]]:
    try:
        import sqlite3
        t = (topic or "").strip().lower()
        if not t:
            return []
        db_path = _db_path_from_env()
        rows: List[Dict[str, Any]] = []
        where = "(LOWER(source) LIKE ? OR LOWER(tags) LIKE ? OR LOWER(content) LIKE ?)"
        like = f"%{t}%"
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                f"SELECT id, ts, source, type, tags, content FROM knowledge_blocks WHERE {where} ORDER BY ts DESC, id DESC LIMIT ?",
                (like, like, like, int(limit or 3)),
            )
            for r in cur.fetchall():
                rows.append({
                    "id": f"BLK_{int(r['id'])}",
                    "source": r["source"] or "",
                    "url": r["type"] or "",
                    "tags": r["tags"] or "",
                    "content": r["content"] or "",
                    "ts": int(r["ts"] or 0),
                })
        return rows
    except Exception:
        return []

def _summarize_memory(snippets: List[Dict[str, Any]], max_sentences: int = 5) -> str:
    try:
        if not snippets:
            return ""
        sents: List[str] = []
        for sn in snippets:
            sents += _sentences(str(sn.get("content") or ""))
        # de-dup while preserving order
        seen = set()
        uniq = []
        for s in sents:
            k = s.lower()
            if k in seen:
                continue
            seen.add(k)
            uniq.append(s)
        return " ".join(uniq[: max(1, int(max_sentences or 5))])
    except Exception:
        return ""

def _merge_memory_web(mem_text: str, web_text: str) -> tuple[str, str]:
    try:
        mem_text = (mem_text or "").strip()
        web_text = (web_text or "").strip()
        if mem_text and not web_text:
            base = mem_text
            pts = build_points(mem_text, max_points=5)
            out = base
            if pts:
                out += "\n\nKernpunkte:\n" + "\n".join(f"• {p}" for p in pts)
            return out, ""
        if web_text and not mem_text:
            base = web_text
            pts = build_points(web_text, max_points=5)
            out = base
            if pts:
                out += "\n\nKernpunkte:\n" + "\n".join(f"• {p}" for p in pts)
            return out, ""
        if mem_text and web_text:
            # Fuse: start with a cohesive 2–4 sentence mix, then bullets with additions
            fused = " ".join((_sentences(mem_text)[:3] or []))
            if not fused:
                fused = mem_text[:400]
            new_pts = []
            try:
                mem_set = {s.lower() for s in _sentences(mem_text)}
                for s in _sentences(web_text):
                    if s.lower() not in mem_set:
                        new_pts.append(s)
            except Exception:
                pass
            bullets = (build_points(mem_text, max_points=3) + build_points(" ".join(new_pts), max_points=3))[:6]
            out = fused
            if bullets:
                out += "\n\nKernpunkte:\n" + "\n".join(f"• {p}" for p in bullets)
            delta = "Neue Punkte aus Web ergänzt." if new_pts else ""
            return out, delta
        return "", ""
    except Exception:
        return "", ""

def _origin_label(has_mem: bool, has_web: bool) -> str:
    return "mixed" if (has_mem and has_web) else ("memory" if has_mem else ("web" if has_web else "unknown"))

async def answer_with_memory_check(topic: str, web_ok: bool = True, autonomy: int = 0):
    saved_ids: List[str] = []
    # Memory-first from SQLite
    mem_snips = _fetch_memory_snippets(topic, limit=3)
    mem_text = _summarize_memory(mem_snips, max_sentences=5)
    # Web assist
    web_text = ""; web_sources: List[dict] = []
    if web_ok:
        try:
            _wt, _ws = _answer_from_web(topic, top_k=3)
            web_text = _wt or ""
            web_sources = list(_ws or [])
        except Exception:
            web_text = ""; web_sources = []
    # Synthesis
    ans_text, delta_note = _merge_memory_web(mem_text, web_text)
    if not ans_text:
        # Final fallback: produce a concise, substantive line
        base = mem_text or web_text or f"Hier ist, was ich zu {topic or 'deinem Thema'} weiß:"
        pts = build_points(base, max_points=4)
        ans_text = base if pts == [] else (base + "\n\nKernpunkte:\n" + "\n".join(f"• {p}" for p in pts))
    # Save automatically if allowed
    has_mem = bool(mem_snips)
    has_web = bool(web_text)
    origin = _origin_label(has_mem, has_web)
    if int(autonomy or 0) >= 2 and ans_text:
        try:
            tagset = ["vision", "learned"] + (["web"] if has_web else ["memory"])
            url0 = (web_sources[0].get("url") if web_sources else None)
            blk = save_memory(title=str(topic)[:120], content=ans_text, tags=tagset, url=url0)
            _debug_save("auto_save_initial", blk or {})
            try:
                upsert_addressbook(topic or "", block_file=str((blk or {}).get("file") or ""), url=(url0 or ""))
            except Exception:
                pass
            try:
                bid = _extract_block_id(blk or {})
                if bid:
                    saved_ids.append(str(bid))
                    try:
                        logger.info("[autosave] topic=%s origin=%s blk=%s", str(topic)[:120], origin, bid)
                    except Exception:
                        pass
            except Exception:
                try: logger.error("auto_save_initial: bad blk type: %s", type(blk))
                except Exception: pass
        except Exception:
            pass
    had_memory = has_mem
    had_web = has_web
    mem_count = len(mem_snips)
    try:
        logger.info("[answer_with_memory_check] topic=%s mem_count=%s has_web=%s origin=%s", str(topic)[:120], mem_count, had_web, origin)
    except Exception:
        pass
    return ans_text, origin, delta_note, saved_ids, web_sources, had_memory, had_web, mem_count

def _extract_points(text: str) -> List[str]:
    try:
        import re as _re
        sents = [s.strip() for s in _re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
        return sents[:8]
    except Exception:
        return []

def _years(text: str) -> List[int]:
    try:
        import re as _re
        yrs = [int(y) for y in _re.findall(r"\b(19\d{2}|20\d{2})\b", text or "")]
        return yrs[:6]
    except Exception:
        return []

def _numbers(text: str) -> List[float]:
    try:
        import re as _re
        vals = []
        for m in _re.finditer(r"(?<![\w\d])(\d+[\d\.,]*)", text or ""):
            try:
                v = float(str(m.group(1)).replace('.', '').replace(',', '.'))
                vals.append(v)
            except Exception:
                continue
        return vals[:8]
    except Exception:
        return []

def _has_negation(text: str) -> bool:
    try:
        t = (text or '').lower()
        return any(kw in t for kw in [" nicht ", " kein ", " keine ", " keines ", " never ", "no "])
    except Exception:
        return False

def _token_overlap(a: str, b: str) -> int:
    try:
        import re as _re
        stop = {"der","die","das","und","oder","ein","eine","ist","sind","war","waren","von","im","in","am","zu","für","mit","auf","aus","den","dem","des","the","a","an","of","to","for","and","or","is","are"}
        ta = {w for w in _re.findall(r"[a-zA-ZäöüÄÖÜß0-9]{3,}", a.lower()) if w not in stop}
        tb = {w for w in _re.findall(r"[a-zA-ZäöüÄÖÜß0-9]{3,}", b.lower()) if w not in stop}
        return len(ta & tb)
    except Exception:
        return 0

def compare_memory_with_web(topic: str, web_ok: bool = True):
    mem = _kb_snippets(topic, top_k=5)
    web_sources: List[Dict[str, Any]] = []
    if web_ok:
        _t, web_sources = _answer_from_web(topic, top_k=3)
    mem_points: List[str] = []
    try:
        for m in mem:
            mem_points += _extract_points(m.get("content") or "")
    except Exception:
        pass
    web_points: List[str] = []
    try:
        for w in web_sources:
            sn = w.get("snippet") or ""
            web_points += _extract_points(sn)
    except Exception:
        pass
    # naive delta for new points
    new_points = [p for p in web_points if p and all(p not in mp for mp in mem_points)]

    # Unterschiedlich / Widersprüchlich heuristics
    diffs: List[str] = []
    contras: List[str] = []
    try:
        for wp in web_points:
            best = None
            best_ov = 0
            for mp in mem_points:
                ov = _token_overlap(wp, mp)
                if ov > best_ov:
                    best = mp; best_ov = ov
            if best and best_ov >= 3:
                y_mem = _years(best); y_web = _years(wp)
                n_mem = _numbers(best); n_web = _numbers(wp)
                neg_mem = _has_negation(best); neg_web = _has_negation(wp)
                # Negation mismatch -> contradiction
                if neg_mem != neg_web:
                    contras.append(f"Widerspruch: '{best}' <> '{wp}'")
                    continue
                # Year update
                if y_mem and y_web and max(y_web) != max(y_mem):
                    newer = max(y_web) if max(y_web) > max(y_mem) else max(y_mem)
                    diffs.append(f"Jahresangabe abweichend ({max(y_mem)} ↔ {max(y_web)}), neu: {newer}")
                    continue
                # Numeric difference (>5%)
                try:
                    if n_mem and n_web:
                        a = float(n_mem[0]); b = float(n_web[0])
                        if a > 0 and abs(a-b)/a > 0.05:
                            diffs.append(f"Wert unterscheidet sich (~{a:g} ↔ ~{b:g}) in: '{wp[:80]}'")
                            continue
                except Exception:
                    pass
    except Exception:
        pass

    # Build output sections
    parts: List[str] = [f"Vergleich zu {topic} – neue Punkte, Unterschiede, Widersprüche:"]
    if new_points:
        parts.append("\nNeu:\n- " + "\n- ".join(new_points[:8]))
    else:
        parts.append("\nNeu:\n(keine klaren neuen Punkte)")
    if diffs:
        parts.append("\nUnterschiedlich:\n- " + "\n- ".join(diffs[:8]))
    if contras:
        parts.append("\nWidersprüchlich:\n- " + "\n- ".join(contras[:6]))
    out = "\n".join(parts)
    return out, web_sources

    # Wichtig: Authentifiziere Nutzer vor dem Start des Streams mit kurzlebiger DB‑Session,
    # danach keine offene Session während des SSE‑Streams halten.
    user_ctx: Optional[Dict[str, Any]] = None
    try:
        from ...deps import require_user
        from ...db import SessionLocal
        with SessionLocal() as _db:
            user_ctx = require_user(request, _db)
    except HTTPException:
        # propagate 401/403 as usual
        raise

    # ---- SSE helpers (uniform payloads) -----------------------------------
    def _sse(payload: Dict[str, Any]) -> Dict[str, str]:
        try:
            return {"data": json.dumps(payload, ensure_ascii=False)}
        except Exception:
            # as a last resort, stringify
            return {"data": json.dumps({"error": "encode_failed"})}

    def _sse_err(code: str, detail: str = "", retry_ms: int = 1500) -> Dict[str, str]:
        return _sse({"error": str(code), "detail": (detail or "")[:400], "retry": int(retry_ms)})

    async def event_gen():
        acc = ""
        # Emit an immediate test chunk so clients see the stream is active
        try:
            logger.info("chat_stream: emitting immediate test chunk")
        except Exception:
            pass
        try:
            # Send correlation id so clients can tie logs to UI
            yield _sse({"cid": cid})
            # Raw SSE line for instant visibility (no placeholder text)
            yield "retry: 1500\n\n"
        except Exception:
            # non-fatal; continue normal flow
            pass
        conv_obj = None
        # Frühe Behandlung von Grüßen (kurze Antwort, kein Streaming nötig)
        try:
            low = user_msg.lower()
            if _HOW_ARE_YOU.search(low):
                yield {"data": json.dumps({"delta": "Mir geht’s gut, danke! 😊 Wie geht’s dir – und womit kann ich helfen?"})}
                yield {"data": json.dumps({"done": True})}
                return
            if _GREETING.search(low):
                yield {"data": json.dumps({"delta": "Hallo! 👋 Wie kann ich dir helfen?"})}
                yield {"data": json.dumps({"done": True})}
                return
            calc = try_calc_or_convert(user_msg)
            if calc:
                yield {"data": json.dumps({"delta": calc})}
                yield {"data": json.dumps({"done": True})}
                return
        except Exception:
            pass
        # pre-persist user message if logged in
        try:
            if current and current.get("id"):
                uid = int(current["id"])  # type: ignore
                conv_obj = _ensure_conversation(db, uid, conv_id)
                _save_msg(db, conv_obj.id, "user", user_msg)
        except Exception:
            conv_obj = None
        # LLM-Streaming (mit Persona + Memory‑Hinweisen im Prompt)
        llm_user = user_msg
        note = memory_bullets(mem_hits, bullet_limit)
        if note:
            llm_user += note
        # Default: Bei Fragen zuerst eine kurze Zusammenfassung liefern und Follow-up anbieten
        if is_question(user_msg):
            # Frühzeitig Web versuchen
            ans0, sources0 = try_web_answer(topic or query or user_msg, limit=3)
            if not mem_hits and not ans0:
                x = "Darüber weiß ich noch nichts – ich schaue kurz im Web nach."
                acc += x; yield {"data": json.dumps({"delta": x})}
                ans0, sources0 = try_web_answer(topic or query or user_msg, limit=5)
            if mem_hits or ans0:
                # Nur wenn wirklich Inhalt vorhanden ist, Header + Inhalte streamen
                has_any = bool((ans0 or '').strip()) or bool((note or '').strip())
                if has_any:
                    header = "Kurzfassung:\n\n"
                    acc += header; yield {"data": json.dumps({"delta": header})}
                    if ans0 and ans0.strip():
                        out = ans0.strip()
                        acc += out; yield {"data": json.dumps({"delta": out})}
                    if note and note.strip():
                        acc += note; yield {"data": json.dumps({"delta": note})}
                    if ans0 and ans0.strip():
                        srcs = "\n\n" + format_sources(sources0, limit=2)
                        acc += srcs; yield {"data": json.dumps({"delta": srcs})}
                else:
                    acc += "\n\nLeider habe ich dazu aktuell keine verlässlichen, passenden Quellen gefunden."
                    yield {"data": json.dumps({"delta": "\n\nLeider habe ich dazu aktuell keine verlässlichen, passenden Quellen gefunden."})}
            else:
                acc += "\n\nLeider habe ich dazu aktuell keine verlässlichen Quellen gefunden."
                yield {"data": json.dumps({"delta": "\n\nLeider habe ich dazu aktuell keine verlässlichen Quellen gefunden."})}

            follow = "\n\nMöchtest du mehr? Ich kann vertiefen oder auf bestimmte Bereiche eingehen (z. B. Grundlagen, Arten, Angriffe, Schutz). Sag mir einfach, was dich interessiert."
            acc += follow; yield {"data": json.dumps({"delta": follow})}
            set_last_offer(sid, None); set_offer_context(sid, topic=(topic or user_msg)[:80], seed=user_msg)

            # persist final AI message and retitle
            try:
                if acc and conv_obj:
                    _save_msg(db, conv_obj.id, "ai", acc)
                    asyncio.create_task(_retitle_if_needed(conv_obj.id, user_msg, acc, lang or "de-DE"))
            except Exception:
                pass

            yield {"data": json.dumps({"done": True})}
            return

        # LLM streaming
        _log("info", "start stream_llm persona=%s lang=%s", persona, lang)
        try:
            async for piece in stream_llm(llm_user, system_prompt(persona), lang, persona):
                piece = clean(piece)
                if not piece:
                    continue
                acc += piece
                try:
                    # Avoid logging full text to keep logs small
                    _log("debug", "llm piece len=%d", len(piece))
                except Exception:
                    pass
                yield _sse({"delta": piece})
        except Exception as e:
            try:
                _log("error", "stream_llm raised: %s", e)
            except Exception:
                pass
            # Emit a uniform error and finish the stream so the UI can recover
            yield _sse_err("llm_stream_failed", str(e), 1500)
            yield _sse({"done": True})
            return
            # Inform client we will fallback
            fb = _fallback_reply(user_msg)
            acc = fb
            yield {"data": json.dumps({"delta": fb})}

        # Fallback falls leer/Echo
        if not acc.strip() or acc.strip().lower() == user_msg.lower():
            _log("warning", "fallback_reply_used reason=%s", "empty_or_echo")
            fb = _fallback_reply(user_msg)
            acc = fb
            yield {"data": json.dumps({"delta": fb})}

        # Web-Anreicherung: bei Fragen IMMER zulassen, sonst wenn unsicher ODER keine Memorytreffer
        need_web = is_question(user_msg) or is_uncertain(acc) or (not mem_hits)

        ans, sources = None, []
        learned_text: Optional[str] = None
        learned_url: Optional[str] = None
        block_info: Dict[str, str] = {}

        if need_web:
            try:
                from ...config import settings as _s
                allow_global = bool(getattr(_s, 'ALLOW_NET', True))
            except Exception:
                allow_global = (os.getenv('ALLOW_NET','1')=='1')
            try:
                if allow_global:
                    ans, sources = try_web_answer(topic or user_msg, limit=3)
                elif web_ok:
                    ans, sources = _force_web_answer(topic or user_msg, limit=3)
            except Exception:
                ans, sources = None, []

        if ans:
            s = ans.strip()
            learned_text = s
            learned_url  = sources[0].get("url") if (sources and sources[0].get("url")) else None
            out = s + format_sources(sources, limit=2)
            acc += out
            yield {"data": json.dumps({"delta": out})}
            if int(autonomy or 0) >= 1:
                block_info = save_memory(
                    title=(topic or user_msg)[:120], content=s, tags=["web","learned"], url=learned_url, chain_hint=bool(chain)
                )
        if topic and (block_info.get("file") or learned_url):
            upsert_addressbook(topic, block_file=block_info.get("file",""), url=learned_url or "")
            enqueue_enrichment(topic)

        # Relevante Notizen, falls kein Web-Override
        if not need_web and mem_hits:
            note = memory_bullets(mem_hits)
            if note:
                acc += note
                yield {"data": json.dumps({"delta": note})}

        # Auto-Lernen eigener Antwort (nicht Web), wenn substanziell
        if (not need_web) and (not mem_hits) and acc and len(acc) > 120 and "Quellen:" not in acc and not _GREETING.search(user_msg.lower()) and int(autonomy or 0) >= 2:
            try:
                learned_text = acc
                block_info = save_memory(
                    title=(topic or user_msg)[:120], content=learned_text, tags=["learned"], url=None, chain_hint=False
                )
                if topic and block_info.get("file"):
                    upsert_addressbook(topic, block_file=block_info["file"])
                    enqueue_enrichment(topic)
            except Exception:
                pass

        # Kurz-Recap streamen (falls gelernt)
        if learned_text:
            recap = "\n\n(Kurz gelernt)\n" + short_summary(learned_text, max_chars=280)
            yield {"data": json.dumps({"delta": recap})}

        # Angebot einmalig
        if any(k in user_msg.lower() for k in ["erklären", "hilfe", "verstehen", "überblick", "was ist", "erklärung"]):
            offer = "\n\nSoll ich es kurz erklären, zusammenfassen oder einen kleinen Plan vorschlagen?"
            yield {"data": json.dumps({"delta": offer})}
            set_last_offer(sid, "kurz")
            set_offer_context(sid, topic=(topic or user_msg)[:80], seed=user_msg)
        else:
            set_last_offer(sid, None)  # kein offenes Angebot merken
        # Always finish the SSE stream so the client can finalize the bubble
        yield {"data": json.dumps({"done": True})}
        # persist final AI message and retitle
        try:
            if acc and conv_obj:
                _save_msg(db, conv_obj.id, "ai", acc)
                asyncio.create_task(_retitle_if_needed(conv_obj.id, user_msg, acc, lang or "de-DE"))
        except Exception:
            pass
        # audit at end of stream
        try:
            _audit_chat({
                "ts": int(time.time()),
                "sid": sid,
                "persona": persona,
                "lang": lang,
                "user": user_msg,
                "reply": acc[:4000],
                "topic": topic,
                "stream": True,
            })
        except Exception:
            pass
        

    # Sende regelmäßige Heartbeats, damit Reverse-Proxies die Verbindung
    # nicht wegen Inaktivität beenden (502/504 Timeouts)
    if EventSourceResponse is None:
        # Robust SSE fallback using StreamingResponse – browsers can consume this with EventSource
        _log("warn", "EventSourceResponse unavailable – using StreamingResponse SSE fallback")
        async def _fallback_sse():
            try:
                # minimal thinking indicator
                yield b": ping\n\n"
                user = user_msg
                system = system_prompt(persona)
                out = await call_llm_once(user, system, lang, persona)
                txt = clean(out or "")
                data = json.dumps({"text": txt, "done": False}, ensure_ascii=False).encode("utf-8")
                yield b"data: " + data + b"\n\n"
                yield b"data: {\"done\": true}\n\n"
            except Exception as e:
                err = json.dumps({"error": str(e), "done": True}).encode("utf-8")
                yield b"data: " + err + b"\n\n"
        headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        return StreamingResponse(_fallback_sse(), media_type="text/event-stream", headers=headers)
    _log("info", "starting SSE EventSourceResponse (setup) t=%.3fs", (time.time()-t0))
    async def _safe_event_gen():
        try:
            async for _chunk in event_gen():
                yield _chunk
        except Exception as _e:
            try:
                _log("error", "event_gen failed: %s", _e)
            except Exception:
                pass
            # include cid before error for correlation
            try: yield _sse({"cid": cid})
            except Exception: pass
            yield _sse_err("server_error", str(_e), 1500)
            yield _sse({"done": True})
    resp = _sse_response(_safe_event_gen())
    if resp is not None:
        return resp
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
# -------------------------------------------------
# WebSocket (optional Alternative zu SSE)
# -------------------------------------------------
@router.websocket("/ws")
async def chat_ws(ws: WebSocket):
    await ws.accept()
    try:
        # Generate a new conversation ID for this WebSocket connection
        import uuid
        conv_id = str(uuid.uuid4())
        
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if not isinstance(msg, dict) or "message" not in msg:
                    await ws.send_json({"error": "invalid_message_format"})
                    continue
                
                # Ensure conv_id is set for this connection
                if "conv_id" not in msg or not msg["conv_id"]:
                    msg["conv_id"] = conv_id
                
                # Process the message
                response = await chat_once(
                    ChatIn(**msg),
                    request=Request(scope={"type": "websocket", "headers": {}}),
                    db=next(get_db()),
                    current={"id": None}
                )
                
                # Always include conv_id in the response
                response["conv_id"] = msg["conv_id"]
                
                # Send the full response including quick_replies
                await ws.send_json(response)
                
            except json.JSONDecodeError:
                await ws.send_json({"error": "invalid_json", "conv_id": conv_id})
            except Exception as e:
                await ws.send_json({"error": str(e), "conv_id": conv_id})
    except WebSocketDisconnect:
        pass

# -------------------------------------------------
# Feedback + Addressbook
# -------------------------------------------------
@router.post("/feedback")
async def post_feedback(body: FeedbackIn):
    msg = (body.message or "").strip()
    status = (body.status or "").strip().lower()
    if not msg or status not in ("ok", "wrong"):
        raise HTTPException(400, "invalid feedback")

    # als Lern-Block ablegen
    save_memory(
        title=f"Feedback:{msg[:50]}",
        content=f"Feedback: {status}\nMessage: {msg}",
        tags=["feedback"] + (["correction"] if status == "wrong" else [])
    )
    return {"ok": True}

    

# -------------------------------------------------
# Viewer APIs: Block-Detail + Rating (Papa-/Admin-Modus)
# -------------------------------------------------

def _load_addrbook() -> Dict[str, Any]:
    try:
        if ADDRBOOK_PATH.exists():
            return json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8")) or {"blocks": []}
    except Exception:
        pass
    return {"blocks": []}

def _save_addrbook(data: Dict[str, Any]) -> None:
    try:
        ADDRBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
        ADDRBOOK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _require_papa_mode():
    if os.getenv("PAPA_MODE", "").lower() not in {"1", "true", "on"}:
        raise HTTPException(status_code=403, detail="Papa-Modus ist nicht aktiviert")

@router.get("/viewer/block")
async def get_block_detail(
    block_id: str = Query(..., min_length=3),
    current=Depends(get_current_user_required),
):
    """
    Liefert den JSON-Inhalt eines Blocks plus Meta aus dem Adressbuch.
    Zugelassen: Papa-Mode ODER Rolle admin.
    """
    # Guard
    is_admin = _has_any_role(current, {"admin"})
    if not is_admin:
        _require_papa_mode()

    ab = _load_addrbook()
    blocks: List[dict] = ab.get("blocks", [])
    meta = next((b for b in blocks if str(b.get("block_id")) == str(block_id)), None)
    if not meta:
        raise HTTPException(status_code=404, detail="Block nicht gefunden")

    path = meta.get("path") or ""
    if not path:
        raise HTTPException(status_code=422, detail="Block hat keinen Pfad")
    p = Path(path)
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve()
    if not p.exists():
        raise HTTPException(status_code=404, detail="Block-Datei fehlt am Pfad")

    try:
        content = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        try:
            content = {"_raw": p.read_text(encoding="utf-8", errors="ignore")}
        except Exception:
            content = {"_error": "unable to read file"}

    return {"ok": True, "meta": meta, "content": content}

@router.post("/viewer/block/rate")
async def rate_block_api(
    payload: Dict[str, Any],
    current=Depends(get_current_user_required),
):
    """
    Aktualisiert das 'rating' eines Blocks (0..1) im Addressbuch.
    Zugelassen: Papa-Mode ODER Rolle admin.
    Body: { "block_id": "...", "rating": 0.0..1.0 }
    """
    # Guard
    is_admin = _has_any_role(current, {"admin"})
    if not is_admin:
        _require_papa_mode()

    block_id = str(payload.get("block_id") or "").strip()
    if not block_id:
        raise HTTPException(status_code=422, detail="block_id fehlt")
    try:
        rating = float(payload.get("rating"))
    except Exception:
        raise HTTPException(status_code=422, detail="rating muss Zahl sein")
    if not (0.0 <= rating <= 1.0):
        raise HTTPException(status_code=422, detail="rating muss zwischen 0.0 und 1.0 sein")

    ab = _load_addrbook()
    blocks: List[dict] = ab.get("blocks", [])
    found = False
    agg_avg = None
    for b in blocks:
        if str(b.get("block_id")) == block_id:
            b["rating"] = rating
            try:
                b["rating_updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
            except Exception:
                b["rating_updated_at"] = int(time.time())
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Block nicht gefunden")

    # Spiegel in Memory-Index (wenn Block bekannt), aggregiert avg/count
    try:
        from ... import memory_store as _mem  # type: ignore
        try:
            reviewer = (current.get("username") or f"uid:{current.get('id')}") if isinstance(current, dict) else ""
        except Exception:
            reviewer = ""
        rec = _mem.rate_block(block_id, float(rating), reviewer=reviewer)
        if isinstance(rec, dict) and "avg" in rec:
            agg_avg = float(rec.get("avg") or rating)
    except Exception:
        pass

    # Wenn Aggregat verfügbar, im Adressbuch widerspiegeln
    try:
        if agg_avg is not None:
            for b in blocks:
                if str(b.get("block_id")) == block_id:
                    b["rating"] = agg_avg
                    break
    except Exception:
        pass

    _save_addrbook(ab)
    return {"ok": True, "block_id": block_id, "rating": float(agg_avg if agg_avg is not None else rating)}

# -------------------------------------------------
# Conversation CRUD (server-side persistence)
# -------------------------------------------------
@router.get("/conversations")
def list_conversations(current=Depends(get_current_user_required), db=Depends(get_db)):
    uid = int(current["id"])  # type: ignore
    items = (
        db.query(Conversation)
        .filter(Conversation.user_id == uid)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return {
        "ok": True,
        "items": [
            {"id": c.id, "title": c.title, "created_at": c.created_at, "updated_at": c.updated_at}
            for c in items
        ]
    }

@router.post("/conversations")
def create_conversation(payload: ConversationCreateIn, current=Depends(get_current_user_required), db=Depends(get_db)):
    uid = int(current["id"])  # type: ignore
    title = (payload.title or "Neue Unterhaltung").strip() or "Neue Unterhaltung"
    c = Conversation(user_id=uid, title=title, created_at=_now(), updated_at=_now())
    db.add(c); db.commit(); db.refresh(c)
    return {"ok": True, "id": c.id, "conversation": {"id": c.id, "title": c.title, "created_at": c.created_at, "updated_at": c.updated_at}}

@router.patch("/conversations/{conv_id}")
def rename_conversation(conv_id: int, payload: ConversationRenameIn, current=Depends(get_current_user_required), db=Depends(get_db)):
    uid = int(current["id"])  # type: ignore
    c = db.query(Conversation).filter(Conversation.id == int(conv_id), Conversation.user_id == uid).first()
    if not c:
        raise HTTPException(404, "not found")
    c.title = (payload.title or c.title).strip() or c.title
    c.updated_at = _now()
    db.add(c); db.commit(); db.refresh(c)
    return {"ok": True}

@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: int, current=Depends(get_current_user_required), db=Depends(get_db)):
    uid = int(current["id"])  # type: ignore
    c = db.query(Conversation).filter(Conversation.id == int(conv_id), Conversation.user_id == uid).first()
    if not c:
        raise HTTPException(404, "not found")
    # delete messages first
    db.query(Message).filter(Message.conv_id == c.id).delete()
    db.delete(c); db.commit()
    return {"ok": True}

@router.get("/conversations/{conv_id}/messages")
def list_messages(conv_id: int, current=Depends(get_current_user_required), db=Depends(get_db)):
    uid = int(current["id"])  # type: ignore
    c = db.query(Conversation).filter(Conversation.id == int(conv_id), Conversation.user_id == uid).first()
    if not c:
        raise HTTPException(404, "not found")
    msgs = (
        db.query(Message)
        .filter(Message.conv_id == c.id)
        .order_by(Message.id.asc())
        .all()
    )
    return {"ok": True, "items": [{"id": m.id, "role": m.role, "text": m.text, "created_at": m.created_at} for m in msgs]}

@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: int, current=Depends(get_current_user_required), db=Depends(get_db)):
    uid = int(current["id"])  # type: ignore
    c = db.query(Conversation).filter(Conversation.id == int(conv_id), Conversation.user_id == uid).first()
    if not c:
        raise HTTPException(404, "not found")
    return {"ok": True, "conversation": {"id": c.id, "title": c.title, "created_at": c.created_at, "updated_at": c.updated_at}}

@router.post("/conversations/{conv_id}/retitle")
async def retitle_conversation(conv_id: int, current=Depends(get_current_user_required)):
    # Open own session inside task
    def _build_seed() -> Tuple[str, str]:
        db = SessionLocal()
        try:
            c = db.query(Conversation).filter(Conversation.id == int(conv_id), Conversation.user_id == int(current["id"]))  # type: ignore
            c = c.first()
            if not c:
                return "", ""
            msgs = (
                db.query(Message)
                .filter(Message.conv_id == c.id)
                .order_by(Message.id.asc())
                .limit(6)
                .all()
            )
            u = next((m.text for m in msgs if m.role == 'user'), '')
            a = next((m.text for m in msgs if m.role == 'ai'), '')
            return (u or (msgs[0].text if msgs else "")), (a or (msgs[1].text if len(msgs) > 1 else ""))
        finally:
            db.close()

    u_text, a_text = _build_seed()
    if not u_text and not a_text:
        raise HTTPException(400, "empty conversation")
    asyncio.create_task(_retitle_if_needed(conv_id, u_text, a_text, "de-DE"))
    return {"ok": True}

# -------------------------------------------------
# POST /api/chat/stream delegating to GET handler
# -------------------------------------------------
@router.post("/stream")
async def chat_stream_post(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    message = str((data.get("message") or "")).strip()
    persona = str(data.get("persona") or "friendly")
    lang = str(data.get("lang") or "de-DE")
    chain = bool(data.get("chain") or False)
    conv_id = data.get("conv_id")
    style = str(data.get("style") or "balanced")
    try:
        bullets = int(data.get("bullets") or 5)
    except Exception:
        bullets = 5
    web_ok = bool(data.get("web_ok") or False)
    try:
        autonomy = int(data.get("autonomy") or 0)
    except Exception:
        autonomy = 0
    # Delegate to the same handler as GET
    return await chat_stream(
        message=message,
        request=request,
        persona=persona,
        lang=lang,
        chain=chain,
        conv_id=conv_id,
        style=style,
        bullets=bullets,
        web_ok=web_ok,
        autonomy=autonomy,
    )


# -------------------------------------------------
# OpenAI-compatible /completions endpoint
# -------------------------------------------------
@router.post("/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint"""
    import httpx
    import os
    
    try:
        body = await request.json()
        model = body.get("model", os.getenv("OLLAMA_MODEL_DEFAULT", "llama3.2:3b"))
        messages = body.get("messages", [])
        stream = body.get("stream", False)
        max_tokens = body.get("max_tokens", 2000)
        temperature = body.get("temperature", 0.7)
        
        if not messages:
            return {"error": "messages required"}
        
        # Forward to Ollama
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        
        ollama_payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            if stream:
                # Stream response
                from fastapi.responses import StreamingResponse
                async def generate():
                    async with client.stream("POST", f"{ollama_host}/api/chat", json=ollama_payload) as resp:
                        async for line in resp.aiter_lines():
                            if line:
                                yield f"{line}\n"
                return StreamingResponse(generate(), media_type="text/event-stream")
            else:
                # Non-stream response
                resp = await client.post(f"{ollama_host}/api/chat", json=ollama_payload)
                data = resp.json()
                
                # Convert Ollama format to OpenAI format
                return {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": data.get("message", {}).get("content", "")
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                        "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
                    }
                }
    except Exception as e:
        return {"error": str(e), "detail": "Chat completion failed"}
