import os
import json, time
from datetime import date, datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from ...deps import get_db, set_cookie, clear_cookie, require_user, create_session
from ...models import User
from .schemas import RegisterIn, LoginIn
from sqlalchemy import func, text
from .crypto import hash_pw, check_pw
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from netapi.deps import get_current_user_opt, is_kid
from netapi.deps import get_current_user_required as _cur_user, require_role as _require_role
from ...jwt_utils import encode_jwt
from ...jwt_utils import decode_jwt
from ..timeflow.events import record_timeflow_event
try:
    from ..admin.router import write_audit  # type: ignore
except Exception:
    def write_audit(*args, **kwargs):  # type: ignore
        return None

router = APIRouter(prefix="/api", tags=["auth"])

# -------------------------
# Registration guardrails
# -------------------------
_REGISTER_RATE_BUCKET: Dict[str, List[float]] = {}


def _rate_allow(ip: str, key: str, *, limit: int = 5, per_seconds: int = 60) -> bool:
    now = time.time()
    bucket_key = f"{ip}:{key}"
    bucket = _REGISTER_RATE_BUCKET.setdefault(bucket_key, [])
    while bucket and now - bucket[0] > per_seconds:
        bucket.pop(0)
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


def _min_password_len() -> int:
    try:
        return max(6, int(os.getenv("KI_MIN_PASSWORD_LEN", "10")))
    except Exception:
        return 10

def _validate_birthdate(bd: str | None) -> str | None:
    if not bd: return None
    try: date.fromisoformat(bd); return bd
    except Exception: raise HTTPException(400, "birthdate must be YYYY-MM-DD")

@router.post("/register")
def register(payload: RegisterIn, request: Request, db=Depends(get_db)):
    ip = (request.client.host if request.client else "?")
    if not _rate_allow(ip, "register", limit=5, per_seconds=60):
        raise HTTPException(429, "rate_limited")

    u_name = (payload.username or "").strip().lower()
    email = str(payload.email or "").strip().lower()
    pw = str(payload.password or "")
    display_name = (payload.name or "").strip()[:120] if getattr(payload, "name", None) else ""

    if not u_name or not email or not pw:
        raise HTTPException(400, "missing_fields")

    # Username policy: min 3, only [a-z0-9._-]
    try:
        import re

        if not re.fullmatch(r"[a-z0-9._-]{3,50}", u_name):
            raise HTTPException(400, "invalid_username")
    except HTTPException:
        raise
    except Exception:
        # If regex fails for some unexpected reason, still avoid creating weird usernames.
        raise HTTPException(400, "invalid_username")

    min_pw = _min_password_len()
    if len(pw) < min_pw:
        raise HTTPException(400, f"password_too_short:{min_pw}")

    # Distinct duplicates (case-insensitive)
    if db.query(User).filter(func.lower(User.username) == u_name).first():
        raise HTTPException(409, "username_exists")
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(409, "email_exists")

    profile = {
        "name": display_name,
        "address": (payload.address.dict() if payload.address else {}),
        "billing": (payload.billing.dict() if payload.billing else {}),
    }
    now_dt = datetime.utcnow()
    user = User(
        username=u_name,
        email=email,
        password_hash=hash_pw(pw),
        role="user",
        tier="user",
        is_papa=False,
        plan="free",
        plan_until=0,
        birthdate=_validate_birthdate(payload.birthdate),
        address=json.dumps(profile, ensure_ascii=False),
        created_at=now_dt,
        updated_at=now_dt,
    )
    db.add(user); db.commit(); db.refresh(user)

    out: Dict[str, Any] = {"ok": True, "user_id": int(user.id)}

    # Test-mode: return email verification token for E2E.
    # Staging E2E can enable this via TEST_MODE=1.
    if str(os.getenv("TEST_MODE", "0")).strip() in {"1", "true", "True"}:
        out["email_verification_token"] = encode_jwt(
            {"purpose": "email_verify", "uid": int(user.id), "email": str(user.email or "").lower()},
            exp_seconds=24 * 3600,
        )

    resp = JSONResponse(out)
    # Registrierung: standardmäßig Session-Cookie (kein persistentes Login)
    sid = create_session(db, user_id=int(user.id), remember=False)
    set_cookie(resp, {"sid": sid, "ts": int(time.time())}, remember=False, request=request)
    return resp


class VerifyEmailIn(BaseModel):
    token: str


@router.post("/verify-email")
def verify_email(body: VerifyEmailIn, db=Depends(get_db)):
    payload = decode_jwt((body.token or "").strip())
    if not payload or payload.get("purpose") != "email_verify":
        raise HTTPException(400, "invalid_token")
    try:
        uid = int(payload.get("uid") or 0)
    except Exception:
        uid = 0
    if uid <= 0:
        raise HTTPException(400, "invalid_token")

    # Update is done via SQL to avoid ORM/model drift (DB has these columns).
    now_dt = datetime.utcnow()
    db.execute(
        text(
            """
            UPDATE users
            SET
              email_verified = 1,
              account_status = 'active',
              subscription_status = 'active',
              updated_at = :now_dt
            WHERE id = :uid
            """
        ),
        {"uid": uid, "now_dt": now_dt},
    )
    db.commit()

    # Audit (best-effort)
    try:
        write_audit(
            "email_verify",
            actor_id=uid,
            target_type="user",
            target_id=uid,
            meta={"via": "token"},
        )
    except Exception:
        pass
    return {"ok": True, "user_id": uid}

# Creator-only: create user without affecting current session
@router.post("/admin/users/create")
def admin_create_user(payload: Dict[str, Any], user = Depends(_cur_user), db=Depends(get_db)):
    _require_role(user, {"creator"})
    try:
        username = str(payload.get("username") or "").strip()
        email = str(payload.get("email") or "").strip().lower()
        password = str(payload.get("password") or "")
    except Exception:
        raise HTTPException(400, "invalid payload")
    if not username or not email or not password:
        raise HTTPException(400, "username, email, password required")
    # uniqueness check
    exists = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if exists:
        raise HTTPException(409, "username or email already exists")
    role = str(payload.get("role") or "user").strip().lower() or "user"
    # optional fields
    plan = str(payload.get("plan") or "free").strip().lower() or "free"
    plan_until = int(payload.get("plan_until") or 0)
    daily_quota = payload.get("daily_quota")
    try:
        if daily_quota is not None:
            daily_quota = int(daily_quota)
    except Exception:
        daily_quota = None
    now_dt = datetime.utcnow()
    u = User(
        username=username,
        email=email,
        password_hash=hash_pw(password),
        role=role,
        plan=plan,
        plan_until=plan_until,
        created_at=now_dt,
        updated_at=now_dt,
    )
    if daily_quota is not None and hasattr(u, 'daily_quota'):
        u.daily_quota = int(daily_quota)
    db.add(u); db.commit(); db.refresh(u)
    # Audit
    try:
        write_audit(
            "user_create",
            actor_id=int(user.get("id") or 0),
            target_type="user",
            target_id=int(u.id or 0),
            meta={"role": u.role, "plan": u.plan, "plan_until": int(u.plan_until or 0)},
        )
    except Exception:
        pass
    return {"ok": True, "user": {"id": u.id, "username": u.username, "email": u.email, "role": u.role, "plan": u.plan, "plan_until": u.plan_until}}

@router.post("/login")
def login(payload: LoginIn, request: Request, db=Depends(get_db)):
    """Login accepts username OR email in the `username` field.
    Returns ok + user info and a short-lived JWT token, and also sets the session cookie.
    """
    uname = (payload.username or "").strip()
    if not uname or not payload.password:
        raise HTTPException(400, "missing credentials")
    # Case-insensitive lookup for username OR email. Multiple rows may match
    # (e.g., legacy 'Gerald' and new 'gerald'). Try exact username match first,
    # then email; verify password for each candidate.
    u_l = uname.lower()
    candidates = db.query(User).filter((func.lower(User.username) == u_l) | (func.lower(User.email) == u_l)).all() or []
    user = None
    # Prefer username matches over email matches
    uname_matches = [u for u in candidates if str(getattr(u, 'username', '')).lower() == u_l]
    email_matches = [u for u in candidates if str(getattr(u, 'email', '')).lower() == u_l]
    for u in (uname_matches + email_matches):
        if check_pw(payload.password, getattr(u, 'password_hash', '') or ""):
            user = u
            break
    if not user:
        raise HTTPException(401, "invalid credentials")
    # Enforce account status
    status = (getattr(user, 'status', 'active') or 'active').lower()
    if status in {"suspended", "banned", "deleted"}:
        raise HTTPException(403, f"account {status}")
    # Create JWT for frontend localStorage use
    claims = {"uid": int(user.id), "username": user.username, "role": user.role or "user"}
    token = encode_jwt(claims, exp_seconds=24*3600)
    resp = JSONResponse({
        "ok": True,
        "token": token,
        "user": {"id": user.id, "username": user.username, "role": user.role, "plan": user.plan, "plan_until": user.plan_until}
    })
    # If payload.remember True, then 30 days; else session-cookie until browser close
    sid = create_session(db, user_id=int(user.id), remember=bool(payload.remember))
    set_cookie(resp, {"sid": sid, "ts": int(time.time())}, remember=payload.remember, request=request)
    try:
        record_timeflow_event(
            db,
            user_id=user.id,
            event_type="login",
            meta={"username": user.username, "remember": bool(payload.remember)},
            auto_commit=True,
        )
    except Exception:
        pass
    return resp

async def _get_user_subminds(user: Any) -> List[Any]:
    """
    Liefert die Subminds des Users.
    Passe diese Funktion an deine Datenquelle an (DB/JSON).
    Aktuell: schaut in user.subminds oder gibt [] zurück.
    """
    sm = getattr(user, "subminds", None)
    if isinstance(sm, list):
        return sm
    return []

def _normalize_roles(user: Dict[str, Any]) -> List[str]:
    # Basisrolle aus DB
    base = str(user.get("role", "user")).lower()
    roles = {base, "user"}  # "user" immer für eingeloggte Accounts
    # Zusätzliche Quellen tolerant zusammenführen (falls vorhanden)
    extra_sources = [
        user.get("roles"), user.get("permissions"), user.get("groups"), user.get("group"),
        user.get("claims"), user.get("scopes"), user.get("authorities"),
    ]
    for src in extra_sources:
        if not src:
            continue
        try:
            if isinstance(src, str):
                roles.update([x.strip().lower() for x in src.split(',') if x and x.strip()])
            elif isinstance(src, list):
                roles.update([str(x).strip().lower() for x in src if x is not None])
            elif isinstance(src, set):
                roles.update([str(x).strip().lower() for x in src])
        except Exception:
            continue
    return sorted(r for r in roles if r)

def _is_creator(roles: List[str]) -> bool:
    return "creator" in roles or "owner" in roles

def _is_admin(roles: List[str]) -> bool:
    return "admin" in roles

def _is_papa(roles: List[str], user: Dict[str, Any]) -> bool:
    if "papa" in roles:
        return True
    # Bool-Flags aus dem Userobjekt unterstützen
    return bool(user.get("is_papa") or user.get("papa") or user.get("isPapa"))

def _get_subminds(user: Dict[str, Any]) -> List[Any]:
    """
    Placeholder: liefert [].
    Falls du später Subminds in der DB/JSON hinterlegst, hier befüllen.
    Beispiele:
      - aus user.get("subminds", [])
      - separate Tabelle/Relation (via ORM), etc.
    """
    sm = user.get("subminds")
    return sm if isinstance(sm, list) else []

@router.get("/me")
def me(current = Depends(get_current_user_opt)) -> Dict[str, Any]:
    if not current:
        return {"auth": False, "user": None}

    # 'current' ist das Dict aus require_user/current_user_optional
    # -> enthält id, username, role, plan, plan_until
    roles = _normalize_roles(current)
    # is_papa ableiten und Rolle ggf. ergänzen, damit das Frontend sie sicher sieht
    is_papa = _is_papa(roles, current)
    # Creator soll Papa-Rechte im UI implizieren
    if (is_papa or ("creator" in roles)) and "papa" not in roles:
        roles = sorted(set(roles) | {"papa"})
    user_out: Dict[str, Any] = {
        "id": current.get("id"),
        "username": current.get("username"),
        "email": current.get("email"),        # optional/nicht vorhanden => None
        "name": current.get("username"),      # Fallback
        "role": current.get("role", "user"),
        "roles": roles,
        "is_creator": _is_creator(roles),
        "is_admin": _is_admin(roles),
        "is_papa": is_papa,
        "birthdate": current.get("birthdate"),
        "is_kid": is_kid(current),
        "plan": current.get("plan", "free"),
        "plan_until": current.get("plan_until", 0),
        "created_at": current.get("created_at", 0),
        "subminds": _get_subminds(current),
        # Derived capabilities for frontend gating
        "caps": {
            # Nur Creator darf Benutzer direkt verwalten (Listen/Anlegen/Rollen/Status)
            "can_manage_users": _is_creator(roles),
            # Block Viewer sichtbar für admin/creator/papa
            "can_view_block_viewer": (_is_admin(roles) or _is_creator(roles) or is_papa),
            # Sign/rehash erfordern administrative Rechte (papa/admin/creator)
            "can_sign_blocks": (_is_admin(roles) or is_papa or _is_creator(roles) or ("worker" in roles)),
            "can_rehash_blocks": (_is_admin(roles) or is_papa or _is_creator(roles)),
            # Adminbereich (Admin-Menüs) für admin/creator
            "can_view_admin": (_is_admin(roles) or _is_creator(roles)),
        },
    }
    return {"auth": True, "user": user_out}


@router.get("/account")
def account(current = Depends(get_current_user_opt)) -> Dict[str, Any]:
    # Minimal alias for M3.3 E2E/UI compatibility.
    return me(current)  # type: ignore[misc]

# ---------------- Creator-only: Roles Admin ----------------
@router.get("/admin/users")
def admin_list_users(user = Depends(_cur_user), db=Depends(get_db)):
    _require_role(user, {"creator"})
    rows = db.query(User).all()
    out = []
    for u in rows:
        out.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role or "user",
            "tier": getattr(u, 'tier', 'user') or 'user',
            "daily_quota": int(getattr(u, 'daily_quota', 20) or 20),
            "plan": u.plan or 'free',
            "plan_until": int(u.plan_until or 0),
            "birthdate": getattr(u, 'birthdate', None),
            "is_kid": bool(is_kid({"birthdate": getattr(u, 'birthdate', None)})),
            "status": getattr(u, 'status', 'active') or 'active',
            "suspended_reason": getattr(u, 'suspended_reason', ''),
        })
    return {"ok": True, "items": out}

@router.post("/admin/users/set-role")
def admin_set_role(payload: Dict[str, Any], user = Depends(_cur_user), db=Depends(get_db)):
    _require_role(user, {"creator"})
    try:
        uid = int(payload.get("user_id"))
    except Exception:
        raise HTTPException(400, "user_id required")
    role = str(payload.get("role") or "").strip().lower() or None
    tier = str(payload.get("tier") or "").strip().lower() or None
    dq = payload.get("daily_quota")
    if dq is not None:
        try:
            dq = int(dq)
        except Exception:
            raise HTTPException(400, "daily_quota must be int")
    rec = db.query(User).filter(User.id == uid).first()
    if not rec:
        raise HTTPException(404, "user not found")
    if role:
        rec.role = role
    if hasattr(rec, 'tier') and tier:
        setattr(rec, 'tier', tier)
    if hasattr(rec, 'daily_quota') and dq is not None:
        setattr(rec, 'daily_quota', dq)
    rec.updated_at = datetime.utcnow()
    db.add(rec); db.commit(); db.refresh(rec)
    # Audit
    try:
        write_audit(
            "set_role",
            actor_id=int(user.get("id") or 0),
            target_type="user",
            target_id=int(rec.id or 0),
            meta={
                "role": rec.role,
                "tier": getattr(rec, 'tier', None),
                "daily_quota": getattr(rec, 'daily_quota', None),
            },
        )
    except Exception:
        pass
    return {"ok": True, "user": {"id": rec.id, "role": rec.role, "tier": getattr(rec, 'tier', None), "daily_quota": getattr(rec, 'daily_quota', None)}}

# New: Creator-only set-status (suspend/ban/delete/restore)
@router.post("/admin/users/set-status")
def admin_set_status(payload: Dict[str, Any], user = Depends(_cur_user), db=Depends(get_db)):
    _require_role(user, {"creator"})
    try:
        uid = int(payload.get("user_id"))
    except Exception:
        raise HTTPException(400, "user_id required")
    new_status = str(payload.get("status") or "").strip().lower()
    if new_status not in {"active","suspended","banned","deleted"}:
        raise HTTPException(400, "status must be one of active|suspended|banned|deleted")
    reason = str(payload.get("reason") or "").strip()
    rec = db.query(User).filter(User.id == uid).first()
    if not rec:
        raise HTTPException(404, "user not found")
    now = int(time.time())
    rec.status = new_status
    if new_status in {"suspended","banned"}:
        rec.suspended_reason = reason[:500]
        rec.deleted_at = 0
    elif new_status == "deleted":
        rec.deleted_at = now
        rec.suspended_reason = reason[:500]
    else:
        # active
        rec.suspended_reason = ""
        rec.deleted_at = 0
    rec.updated_at = datetime.utcnow()
    db.add(rec); db.commit(); db.refresh(rec)
    # Audit
    try:
        write_audit(
            "user_set_status",
            actor_id=int(user.get("id") or 0),
            target_type="user",
            target_id=int(rec.id or 0),
            meta={"status": rec.status, "reason": rec.suspended_reason},
        )
    except Exception:
        pass
    return {"ok": True, "user": {"id": rec.id, "status": rec.status, "deleted_at": rec.deleted_at, "reason": rec.suspended_reason}}
@router.api_route("/logout", methods=["GET", "POST"])
def logout(request: Request):
    resp = JSONResponse({"ok": True}); clear_cookie(resp, request=request); return resp

# Issue JWT tokens for API clients (optional, in addition to cookie sessions)
@router.post("/token")
def issue_token(payload: Optional[LoginIn] = None, request: Request = None, db=Depends(get_db)):
    """
    Returns a signed HS256 JWT usable as Authorization: Bearer <token>.
    - If credentials are provided in payload, authenticates and issues a token.
    - Otherwise, if a valid session cookie is present, issues a token for that user.
    """
    user: Optional[User] = None
    if payload and payload.username:
        user = db.query(User).filter(User.username == payload.username.strip()).first()
        if not user or not check_pw(payload.password, user.password_hash or ""):
            raise HTTPException(401, "invalid credentials")
    else:
        # Use current session
        try:
            cur = require_user(request, db)
            user = db.query(User).filter(User.id == int(cur.get("id"))).first()
        except Exception:
            user = None
    if not user:
        raise HTTPException(401, "authentication required")
    claims = {"uid": int(user.id), "username": user.username, "role": user.role or "user"}
    # Default 24h token
    token = encode_jwt(claims, exp_seconds=24*3600)
    return {"ok": True, "token": token, "expires_in": 24*3600}

# ---- Legacy alias under /api/auth/* to avoid 404s ---------------------------------
# NOTE: Main router already has prefix '/api'. Using '/auth' here ensures final path '/api/auth/*'.
legacy = APIRouter(prefix="/auth", tags=["auth"])

@legacy.post("/register")
def _legacy_register(payload: RegisterIn, request: Request, db=Depends(get_db)):
    return register(payload, request, db)  # type: ignore[arg-type]

@legacy.post("/login")
def _legacy_login(payload: LoginIn, request: Request, db=Depends(get_db)):
    return login(payload, request, db)  # reuse handler

@legacy.get("/me")
def _legacy_me(current = Depends(get_current_user_opt)):
    return me(current)  # type: ignore[misc]

@legacy.api_route("/logout", methods=["GET", "POST"])
def _legacy_logout(request: Request):
    return logout(request)

@legacy.post("/token")
def _legacy_token(payload: Optional[LoginIn] = None, request: Request = None, db=Depends(get_db)):
    return issue_token(payload, request, db)

# Mount legacy into main router so app.py doesn't need to include twice
router.include_router(legacy)
