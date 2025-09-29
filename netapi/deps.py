# netapi/deps.py
import time, json
from typing import Optional, Dict, Any
from fastapi import HTTPException, Request
import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from .config import settings
from .jwt_utils import decode_jwt
from .db import SessionLocal
from .models import User
from fastapi import Depends

COOKIE_NAME = "ki_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 Tage (nur für "remember")
try:
    DEFAULT_FREE_DAILY_QUOTA = int(__import__('os').getenv('FREE_DAILY_QUOTA', '20'))
except Exception:
    DEFAULT_FREE_DAILY_QUOTA = 20

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.KI_SECRET)

def set_cookie(resp, payload: Dict[str, Any], *, remember: bool = False, request: Optional[Request] = None) -> None:
    """
    Setzt das Session-Cookie.
    - Ohne "remember": Session-Cookie (löscht sich beim Schließen des Browsers).
    - Mit  "remember": Persistentes Cookie mit Max-Age (30 Tage).
    """
    token = _serializer().dumps(payload)
    cookie_kwargs: Dict[str, Any] = {
        "httponly": True,
        "samesite": "lax",
        "path": "/",
    }
    # Nur bei "remember" ein dauerhaftes Cookie setzen
    if remember:
        cookie_kwargs["max_age"] = COOKIE_MAX_AGE
    # Optional: secure nur für https (aber lokal zulassen)
    try:
        if request is not None and request.url.scheme == "https":
            cookie_kwargs["secure"] = True
        # Für ki-ana.at Domain explizit setzen
        if request is not None and "ki-ana.at" in str(request.url.hostname or ""):
            cookie_kwargs["domain"] = ".ki-ana.at"
    except Exception:
        pass
    resp.set_cookie(COOKIE_NAME, token, **cookie_kwargs)

def clear_cookie(resp) -> None:
    resp.delete_cookie(COOKIE_NAME, path="/")
    # Auch für ki-ana.at Domain löschen
    resp.delete_cookie(COOKIE_NAME, path="/", domain=".ki-ana.at")

def read_cookie(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(COOKIE_NAME)
    if not token: return None
    try:
        data = _serializer().loads(token, max_age=COOKIE_MAX_AGE)
        return data if isinstance(data, dict) else None
    except (BadSignature, SignatureExpired):
        return None

def read_bearer_jwt(request: Request) -> Optional[Dict[str, Any]]:
    try:
        auth = request.headers.get('Authorization') or request.headers.get('authorization')
        if not auth:
            return None
        if not auth.lower().startswith('bearer '):
            return None
        token = auth.split(' ', 1)[1].strip()
        payload = decode_jwt(token)
        if not payload or not isinstance(payload, dict):
            return None
        return payload
    except Exception:
        return None

def read_identity(request: Request) -> Optional[Dict[str, Any]]:
    """Prefers Bearer JWT (Authorization header), falls back to session cookie."""
    p = read_bearer_jwt(request)
    if p:
        return p
    return read_cookie(request)

def require_user(request: Request, db) -> Dict[str, Any]:
    # 1) Try cookie/JWT identity
    data = read_identity(request)
    # 2) Fallback: ADMIN_API_TOKEN (static Bearer token) grants creator access for automation/CLI
    if not data:
        try:
            auth = request.headers.get('Authorization') or request.headers.get('authorization') or ''
            if auth.lower().startswith('bearer '):
                token = auth.split(' ', 1)[1].strip()
                admin_tok = os.getenv('ADMIN_API_TOKEN', '').strip()
                if admin_tok and token == admin_tok:
                    # synthesize a creator principal
                    return {
                        "id": 0,
                        "username": "admin-token",
                        "role": "creator",
                        "tier": "creator",
                        "plan": "creator",
                        "plan_until": 0,
                        "daily_quota": DEFAULT_FREE_DAILY_QUOTA,
                        "is_papa": False,
                    }
        except Exception:
            pass
        raise HTTPException(401, "login required")
    uid = int(data.get("uid") or 0)
    user = db.query(User).filter(User.id == uid).first()
    if not user: raise HTTPException(401, "unknown user")
    # Derive simple flags from existing columns (role) and optional DB column is_papa
    base_role = str(getattr(user, 'role', 'user') or 'user').lower()
    tier = str(getattr(user, 'tier', 'user') or 'user').lower()
    is_papa_flag = (base_role == "papa") or (tier.startswith('papa')) or bool(getattr(user, 'is_papa', False))
    ident = {
        "id": user.id, "username": user.username,
        "role": base_role or "user", "tier": tier or 'user',
        "plan": user.plan or "free",
        "plan_until": int(user.plan_until or 0),
        "daily_quota": int(getattr(user, 'daily_quota', DEFAULT_FREE_DAILY_QUOTA) or DEFAULT_FREE_DAILY_QUOTA),
        "birthdate": getattr(user, 'birthdate', None),
        # Papa flag so /api/me and nav can expose Papa UI
        "is_papa": is_papa_flag,
    }
    # Expose effective roles and is_admin derived from role string + feature flags
    try:
        eff_roles = sorted(list(_role_set({"role": base_role, "roles": []})))
        ident["roles"] = eff_roles
        # Compute is_admin per spec: admin OR (creator AND KI_CREATOR_FULL_ACCESS=="1")
        try:
            cfa = os.getenv("KI_CREATOR_FULL_ACCESS", "0") or "0"
        except Exception:
            cfa = "0"
        ident["is_admin"] = ("admin" in eff_roles) or (("creator" in eff_roles) and (str(cfa).strip() == "1"))
    except Exception:
        ident["roles"] = [base_role] if base_role else ["user"]
        ident["is_admin"] = (base_role == "admin") or ((base_role == "creator") and (str(os.getenv("KI_CREATOR_FULL_ACCESS", "0")).strip() == "1"))
    return ident

def current_user_optional(request: Request, db) -> Optional[Dict[str, Any]]:
    try: return require_user(request, db)
    except HTTPException: return None

# --- NEW: FastAPI-friendly dependency wrappers ---
def get_current_user_opt(request: Request, db = Depends(get_db)) -> Optional[Dict[str, Any]]:
    """
    FastAPI-Dependency, die den eingeloggten User als Dict liefert
    (oder None, wenn nicht eingeloggt). Nutzt deine bestehende Cookie-Logik.
    """
    return current_user_optional(request, db)

def get_current_user_required(request: Request, db = Depends(get_db)) -> Dict[str, Any]:
    """
    FastAPI-Dependency, die einen eingeloggten User ERZWINGT (401 sonst).
    """
    return require_user(request, db)

# ---- Role helpers (centralized) -------------------------------------------
def _role_set(user: Dict[str, Any] | None) -> set[str]:
    roles: set[str] = set()
    if not user:
        return roles
    try:
        # Accept comma-or-space separated strings, e.g. "creator,admin" or "creator admin"
        base = str(user.get("role") or "").lower().strip()
        if base:
            for token in base.replace(",", " ").split():
                t = token.strip()
                if t:
                    roles.add(t)
        # Also accept dedicated array field 'roles'
        for r in (user.get("roles") or []):
            try:
                t = str(r).lower().strip()
                if t:
                    roles.add(t)
            except Exception:
                continue
        # Normalizations / aliases
        if "admin" in roles:
            roles.add("creator")
        if "creator" in roles:
            roles.add("worker")
        # Any non-guest identity is also a 'user'
        if (base and base != "guest") or roles:
            roles.add("user")
    except Exception:
        pass
    return roles

def has_any_role(user: Dict[str, Any] | None, allowed: set[str] | list[str]) -> bool:
    try:
        return bool(_role_set(user).intersection({str(x).lower() for x in allowed}))
    except Exception:
        return False

def require_role(user: Dict[str, Any] | None, allowed: set[str] | list[str]) -> None:
    if not has_any_role(user, allowed):
        raise HTTPException(403, "forbidden")

def has_tier(user: Dict[str, Any] | None, allowed: set[str] | list[str]) -> bool:
    try:
        if not user: return False
        t = str(user.get('tier') or '').lower().strip()
        return t in {str(x).lower() for x in allowed}
    except Exception:
        return False

def enforce_quota(user: Dict[str, Any] | None, db) -> None:
    """Enforce per-day API quota for 'user' tier. Raises 429 if exceeded."""
    from sqlalchemy import text as _t
    if not user: return
    role = str(user.get('role') or 'user')
    tier = str(user.get('tier') or 'user')
    if role in {'creator','papa','system'} or tier in {'papa_app','papa_os','creator'}:
        return
    # Only enforce for free users
    limit = int(user.get('daily_quota') or DEFAULT_FREE_DAILY_QUOTA)
    uid = int(user.get('id') or 0)
    if uid <= 0 or limit <= 0: return
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    try:
        with db.bind.begin() as conn:  # type: ignore
            row = conn.execute(_t("SELECT count FROM api_usage WHERE user_id=:u AND date=:d"), {"u": uid, "d": today}).fetchone()
            cnt = int(row[0]) if row else 0
            if cnt >= limit:
                raise HTTPException(429, detail={"error":"quota_exceeded","upgrade":True,"limit":limit})
            if row:
                conn.execute(_t("UPDATE api_usage SET count=count+1 WHERE user_id=:u AND date=:d"), {"u": uid, "d": today})
            else:
                conn.execute(_t("INSERT INTO api_usage(user_id,date,count) VALUES(:u,:d,1)"), {"u": uid, "d": today})
    except HTTPException:
        raise
    except Exception:
        # Fail-open on quota storage errors
        return

def is_kid(user: Dict[str, Any] | None, *, min_age: int = 14) -> bool:
    """Return True if user's age is below `min_age` years based on birthdate ('YYYY-MM-DD')."""
    try:
        if not user: return False
        b = str(user.get('birthdate') or '').strip()
        if not b: return False
        # Accept YYYY-MM-DD (primary) and fallback to YYYY/MM/DD
        b = b.replace('/', '-')
        parts = [int(x) for x in b.split('-')[:3]]
        if len(parts) != 3: return False
        y, m, d = parts
        from datetime import date
        bd = date(y, max(1, min(12, m)), max(1, min(31, d)))
        today = date.today()
        age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        return age < int(min_age)
    except Exception:
        return False
