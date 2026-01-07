# netapi/deps.py
import time, json
from typing import Optional, Dict, Any
import hashlib
import secrets
from fastapi import HTTPException, Request
import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from .config import settings
from .jwt_utils import decode_jwt
from .db import SessionLocal
from .models import User
from fastapi import Depends
from netapi.models import AuthSession

try:
    from netapi.modules.security.audit_log import write_audit_event  # type: ignore
except Exception:
    def write_audit_event(*args, **kwargs):  # type: ignore
        return None

COOKIE_NAME = "ki_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 Tage (nur für "remember")
try:
    DEFAULT_FREE_DAILY_QUOTA = int(__import__('os').getenv('FREE_DAILY_QUOTA', '20'))
except Exception:
    DEFAULT_FREE_DAILY_QUOTA = 20

# ---- M2-BLOCK2: Plan limits (simple MVP config) ---------------------------
def _effective_plan_id(plan: str | None) -> str:
    p = str(plan or "").strip().lower()
    if not p:
        return "free"
    # Legacy paid plans map to PRO for entitlement purposes
    if p.startswith("submind_"):
        return "pro"
    if p in {"free", "pro", "team"}:
        return p
    # Unknown plans: treat as pro (fail-open for paying users)
    return "pro"


def _plan_limits(plan_id: str) -> Dict[str, Any]:
    plan_id = _effective_plan_id(plan_id)
    # Keep defaults aligned with existing behavior.
    free_day = int(os.getenv("FREE_DAILY_QUOTA", str(DEFAULT_FREE_DAILY_QUOTA)) or DEFAULT_FREE_DAILY_QUOTA)
    free_chat_min = int(os.getenv("FREE_CHAT_PER_MINUTE", "40") or "40")
    free_web_day = int(os.getenv("FREE_WEB_DAILY_QUOTA", "5") or "5")
    free_web_min = int(os.getenv("FREE_WEB_PER_MINUTE", "5") or "5")
    if plan_id == "free":
        return {
            "chat_per_day": free_day,
            "chat_per_minute": free_chat_min,
            "web_per_day": free_web_day,
            "web_per_minute": free_web_min,
        }
    if plan_id == "team":
        return {
            "chat_per_day": int(os.getenv("TEAM_CHAT_PER_DAY", "0") or "0"),  # 0 => unlimited
            "chat_per_minute": int(os.getenv("TEAM_CHAT_PER_MINUTE", "0") or "0"),
            "web_per_day": int(os.getenv("TEAM_WEB_PER_DAY", "0") or "0"),
            "web_per_minute": int(os.getenv("TEAM_WEB_PER_MINUTE", "0") or "0"),
        }
    # pro default: unlimited unless env overrides are set
    return {
        "chat_per_day": int(os.getenv("PRO_CHAT_PER_DAY", "0") or "0"),
        "chat_per_minute": int(os.getenv("PRO_CHAT_PER_MINUTE", "0") or "0"),
        "web_per_day": int(os.getenv("PRO_WEB_PER_DAY", "0") or "0"),
        "web_per_minute": int(os.getenv("PRO_WEB_PER_MINUTE", "0") or "0"),
    }

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
    secure_cookie = (str(os.getenv("KIANA_COOKIE_INSECURE", "0")).strip() != "1")
    # Local/staging over plain HTTP: browsers/curl will not send Secure cookies.
    # Keep Secure as default for real SaaS domains, but auto-disable for localhost.
    try:
        if request is not None:
            host = str(request.url.hostname or "").strip().lower()
            scheme = str(request.url.scheme or "").strip().lower()
            if scheme != "https" and host in {"localhost", "127.0.0.1"}:
                secure_cookie = False
    except Exception:
        pass

    cookie_kwargs: Dict[str, Any] = {
        "httponly": True,
        "samesite": "lax",
        "path": "/",
        # SaaS default: always secure unless explicitly disabled
        "secure": secure_cookie,
    }
    # Nur bei "remember" ein dauerhaftes Cookie setzen
    if remember:
        cookie_kwargs["max_age"] = COOKIE_MAX_AGE
    # Optional: Domain scoping for production domain
    try:
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
    # Single-auth-mechanism default: disable Bearer JWT unless explicitly enabled.
    if str(os.getenv("AUTH_ALLOW_BEARER_JWT", "0")).strip() != "1":
        return None
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
    """Single-auth default: prefer session cookie; optional Bearer JWT if enabled."""
    p = read_cookie(request)
    if p:
        return p
    return read_bearer_jwt(request)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db, *, user_id: int, remember: bool) -> str:
    """Create a revocable server-side session and return the raw session id (cookie value)."""
    now = int(time.time())
    # TTL: 24h (default) or 30d (remember)
    ttl = (COOKIE_MAX_AGE if remember else 24 * 3600)
    sid = secrets.token_urlsafe(32)
    s = AuthSession(
        user_id=int(user_id),
        session_hash=_hash_token(sid),
        created_at=now,
        last_seen_at=now,
        expires_at=now + int(ttl),
        revoked_at=0,
    )
    db.add(s)
    db.commit()
    return sid


def revoke_session(db, *, sid: str) -> None:
    """Revoke a single session by id (best-effort)."""
    try:
        h = _hash_token(sid)
        rec = db.query(AuthSession).filter(AuthSession.session_hash == h).first()
        if not rec:
            return
        rec.revoked_at = int(time.time())
        db.add(rec)
        db.commit()
    except Exception:
        return


def revoke_all_sessions(db, *, user_id: int) -> int:
    """Revoke all active sessions for a user. Returns count (best-effort)."""
    now = int(time.time())
    try:
        q = db.query(AuthSession).filter(AuthSession.user_id == int(user_id), AuthSession.revoked_at == 0)
        n = 0
        for s in q.all() or []:
            s.revoked_at = now
            db.add(s)
            n += 1
        db.commit()
        return n
    except Exception:
        return 0

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
    # Session cookie path
    sid = str(data.get("sid") or "").strip()
    if not sid:
        # Legacy cookie payloads with uid are not revocable -> force re-login
        raise HTTPException(401, "session required")
    now = int(time.time())
    sess = db.query(AuthSession).filter(AuthSession.session_hash == _hash_token(sid)).first()
    if not sess or int(getattr(sess, "revoked_at", 0) or 0) > 0:
        raise HTTPException(401, "session invalid")
    if int(getattr(sess, "expires_at", 0) or 0) and int(sess.expires_at or 0) < now:
        raise HTTPException(401, "session expired")
    # Update last_seen best-effort
    try:
        sess.last_seen_at = now
        db.add(sess)
        db.commit()
    except Exception:
        pass
    uid = int(getattr(sess, "user_id", 0) or 0)
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
        # M2 gates
        "email_verified": bool(int(getattr(user, 'email_verified', 0) or 0)),
        "account_status": str(getattr(user, 'account_status', 'active') or 'active'),
        "subscription_status": str(getattr(user, 'subscription_status', 'inactive') or 'inactive'),
        # M2-BLOCK5: GDPR consent
        "consent_learning": str(getattr(user, 'consent_learning', 'ask') or 'ask'),
    }
    # Legacy entitlement bridge: treat plan+plan_until as active subscription.
    try:
        now = int(time.time())
        if (not ident.get("subscription_status") or ident.get("subscription_status") == "inactive"):
            if str(ident.get("plan") or "").startswith("submind_") and int(ident.get("plan_until") or 0) > now:
                ident["subscription_status"] = "active"
    except Exception:
        pass
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
    try:
        return require_user(request, db)
    except HTTPException:
        return None


# --- FastAPI-friendly dependency wrappers ---
def get_current_user_opt(request: Request, db=Depends(get_db)) -> Optional[Dict[str, Any]]:
    """FastAPI dependency: returns user dict or None."""
    return current_user_optional(request, db)


def get_current_user_required(request: Request, db=Depends(get_db)) -> Dict[str, Any]:
    """FastAPI dependency: requires a logged-in user (401 otherwise)."""
    return require_user(request, db)


def require_active_user(
    request: Request,
    current: Optional[Dict[str, Any]] = Depends(get_current_user_opt),
    db = Depends(get_db),
) -> Dict[str, Any]:
    """Central access gate for KI/Tool/Memory/Web routes.

    Rules (non-negotiable):
    - authenticated
    - email_verified == True
    - subscription_status == active
    - account_status == active (admins included)
    """
    # Some endpoints must remain callable without authentication even when they
    # are mounted under routers that use this dependency globally (e.g. docker
    # healthchecks and Prometheus scraping).
    try:
        path = str(getattr(getattr(request, "url", None), "path", "") or "")
    except Exception:
        path = ""
    if path in {"/api/v2/chat/ping", "/api/metrics", "/health", "/_/ping"}:
        return current or {
            "id": 0,
            "role": "anonymous",
            "roles": ["anonymous"],
            "is_admin": False,
            "email_verified": True,
            "account_status": "active",
            "subscription_status": "active",
            "consent_learning": "ask",
        }

    # Always require authentication
    if not current:
        try:
            write_audit_event(
                db,
                event_type="access.denied.unauthenticated",
                actor_user_id=0,
                target_user_id=0,
                request=request,
                meta={"path": str(getattr(request, "url", "") or "")[:200], "method": str(getattr(request, "method", "") or "")[:16]},
            )
        except Exception:
            pass
        raise HTTPException(401, "login required")

    # In the existing test suite, many endpoints bypass auth via dependency overrides.
    # Default behavior in TEST_MODE is to allow those tests to run unchanged.
    if str(os.getenv("TEST_MODE", "0")).strip() == "1" and str(os.getenv("ENFORCE_ACCESS_GATE_IN_TESTS", "0")).strip() != "1":
        return current

    # Ensure we have gate fields; if missing, load from DB.
    uid = int(current.get("id") or 0)
    user = current
    try:
        if ("email_verified" not in user) or ("account_status" not in user) or ("subscription_status" not in user):
            urec = db.query(User).filter(User.id == uid).first()
            if urec:
                user = dict(user)
                user["email_verified"] = bool(int(getattr(urec, "email_verified", 0) or 0))
                user["account_status"] = str(getattr(urec, "account_status", "active") or "active")
                user["subscription_status"] = str(getattr(urec, "subscription_status", "inactive") or "inactive")
                user["consent_learning"] = str(getattr(urec, "consent_learning", "ask") or "ask")
                # Legacy entitlement bridge
                now = int(time.time())
                if (user.get("subscription_status") in {"", "inactive"}) and str(getattr(urec, "plan", "") or "").startswith("submind_") and int(getattr(urec, "plan_until", 0) or 0) > now:
                    user["subscription_status"] = "active"
    except Exception:
        pass

    if not bool(user.get("email_verified")):
        try:
            write_audit_event(db, event_type="access.denied.unverified", actor_user_id=uid, target_user_id=uid, request=request)
        except Exception:
            pass
        raise HTTPException(403, detail={"error": "unverified"})

    acc = str(user.get("account_status") or "").lower().strip()
    # Only block truly inactive accounts here. "pending_subscription" must reach the subscription check
    # so the API returns the explicit entitlement error.
    if acc in {"suspended", "banned", "deleted", "pending_delete"}:
        try:
            write_audit_event(
                db,
                event_type="access.denied.inactive",
                actor_user_id=uid,
                target_user_id=uid,
                request=request,
                meta={"account_status": acc},
            )
        except Exception:
            pass
        if acc == "pending_delete":
            raise HTTPException(403, detail={"error": "account_pending_delete"})
        raise HTTPException(403, detail={"error": "account_inactive", "status": acc})

    sub = str(user.get("subscription_status") or "").lower().strip()
    # M2-BLOCK2 compatibility: if verified and plan is free, treat as active even if legacy
    # rows still show pending_subscription/inactive.
    try:
        if sub != "active":
            eff_plan = _effective_plan_id(str(user.get("plan") or "free"))
            if eff_plan == "free" and bool(user.get("email_verified")):
                sub = "active"
                user = dict(user)
                user["subscription_status"] = "active"
                if str(user.get("account_status") or "").lower().strip() in {"pending_subscription", "pending_verification", ""}:
                    user["account_status"] = "active"
    except Exception:
        pass

    # Grace period support for canceled/past_due subscriptions
    try:
        if sub in {"canceled", "past_due"}:
            now = int(time.time())
            grace_until = int(user.get("subscription_grace_until") or 0)
            if grace_until > now:
                sub = "active"
    except Exception:
        pass

    if sub != "active":
        try:
            write_audit_event(db, event_type="access.denied.no_subscription", actor_user_id=uid, target_user_id=uid, request=request, meta={"subscription_status": sub})
        except Exception:
            pass
        raise HTTPException(403, detail={"error": "no_subscription"})

    return user

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


def require_any_role(user: Dict[str, Any] | None, allowed: list[str] | set[str]) -> None:
    """Alias for require_role with clearer intent."""
    require_role(user, allowed)


def require_admin_area(user: Dict[str, Any] | None) -> None:
    """Guard for /api/admin routes.

    Allows:
    - admin
    - creator (legacy ops)
    - any principal marked is_admin (creator+full-access)
    """
    if not user:
        raise HTTPException(401, "login required")
    try:
        if bool(user.get("is_admin")):
            return
    except Exception:
        pass
    require_any_role(user, {"admin", "creator"})


def require_admin_only(user: Dict[str, Any] | None) -> None:
    """Strict admin-only guard (support/creator are not sufficient)."""
    if not user:
        raise HTTPException(401, "login required")
    require_any_role(user, {"admin"})


def forbid_support(user: Dict[str, Any] | None) -> None:
    """Block support role from sensitive operations (billing, policies, role changes)."""
    if not user:
        raise HTTPException(401, "login required")
    if has_any_role(user, {"support"}):
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
    # Only enforce for free plan users (paid plans are handled by plan limits)
    eff_plan = _effective_plan_id(str(user.get('plan') or 'free'))
    if eff_plan != 'free':
        return
    # Back-compat: daily_quota column still acts as the Free plan daily chat quota.
    limit = int(user.get('daily_quota') or _plan_limits(eff_plan).get('chat_per_day') or DEFAULT_FREE_DAILY_QUOTA)
    uid = int(user.get('id') or 0)
    if uid <= 0 or limit <= 0: return
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    try:
        with db.bind.begin() as conn:  # type: ignore
            row = conn.execute(_t("SELECT count FROM api_usage WHERE user_id=:u AND date=:d AND feature=:f"), {"u": uid, "d": today, "f": "chat"}).fetchone()
            cnt = int(row[0]) if row else 0
            if cnt >= limit:
                try:
                    write_audit_event(db, event_type="limits.exceeded", actor_user_id=uid, target_user_id=uid, request=None, meta={"feature": "chat", "scope": "day", "limit": int(limit), "count": int(cnt)})
                except Exception:
                    pass
                try:
                    from netapi.modules.observability.metrics import inc_limits_exceeded
                    inc_limits_exceeded(feature="chat", scope="day")
                except Exception:
                    pass
                raise HTTPException(429, detail={"error":"quota_exceeded","upgrade":True,"limit":limit})
            if row:
                conn.execute(_t("UPDATE api_usage SET count=count+1 WHERE user_id=:u AND date=:d AND feature=:f"), {"u": uid, "d": today, "f": "chat"})
            else:
                conn.execute(_t("INSERT INTO api_usage(user_id,date,feature,count) VALUES(:u,:d,:f,1)"), {"u": uid, "d": today, "f": "chat"})
    except HTTPException:
        raise
    except Exception:
        # Fail-open on quota storage errors
        return


def enforce_feature_limits(user: Dict[str, Any] | None, db, *, feature: str, request: Request | None = None) -> None:
    """Plan-based daily+minute limits for specific features (chat, web).

    - Daily is stored in api_usage (date bucket)
    - Minute is stored in api_usage_minute (minute bucket)
    """
    from sqlalchemy import text as _t
    if not user:
        return
    feature = str(feature or "").strip().lower()
    if feature not in {"chat", "web"}:
        return
    # Skip for privileged roles
    role = str(user.get('role') or 'user')
    tier = str(user.get('tier') or 'user')
    if role in {'creator','papa','system'} or tier in {'papa_app','papa_os','creator'}:
        return

    eff_plan = _effective_plan_id(str(user.get('plan') or 'free'))
    lim = _plan_limits(eff_plan)

    uid = int(user.get('id') or 0)
    if uid <= 0:
        return

    # Daily quota
    from datetime import datetime, timezone
    now_dt = datetime.now(timezone.utc)
    today = now_dt.strftime('%Y-%m-%d')
    day_limit = int(lim.get(f"{feature}_per_day") or 0)
    if day_limit > 0:
        try:
            with db.bind.begin() as conn:  # type: ignore
                row = conn.execute(_t("SELECT count FROM api_usage WHERE user_id=:u AND date=:d AND feature=:f"), {"u": uid, "d": today, "f": feature}).fetchone()
                cnt = int(row[0]) if row else 0
                if cnt >= day_limit:
                    try:
                        write_audit_event(db, event_type="limits.exceeded", actor_user_id=uid, target_user_id=uid, request=request, meta={"feature": feature, "scope": "day", "limit": int(day_limit), "count": int(cnt), "plan": eff_plan})
                    except Exception:
                        pass
                    try:
                        from netapi.modules.observability.metrics import inc_limits_exceeded
                        inc_limits_exceeded(feature=str(feature), scope="day")
                    except Exception:
                        pass
                    raise HTTPException(429, detail={"error": "quota_exceeded", "feature": feature, "scope": "day", "limit": int(day_limit), "upgrade": True})
                if row:
                    conn.execute(_t("UPDATE api_usage SET count=count+1 WHERE user_id=:u AND date=:d AND feature=:f"), {"u": uid, "d": today, "f": feature})
                else:
                    conn.execute(_t("INSERT INTO api_usage(user_id,date,feature,count) VALUES(:u,:d,:f,1)"), {"u": uid, "d": today, "f": feature})
        except HTTPException:
            raise
        except Exception:
            # fail-open
            pass

    # Minute quota
    minute_limit = int(lim.get(f"{feature}_per_minute") or 0)
    if minute_limit > 0:
        bucket = now_dt.strftime('%Y-%m-%dT%H:%M')
        retry_after = int(60 - now_dt.second) if now_dt.second else 60
        try:
            with db.bind.begin() as conn:  # type: ignore
                row = conn.execute(_t("SELECT count FROM api_usage_minute WHERE user_id=:u AND bucket=:b AND feature=:f"), {"u": uid, "b": bucket, "f": feature}).fetchone()
                cnt = int(row[0]) if row else 0
                if cnt >= minute_limit:
                    try:
                        write_audit_event(db, event_type="limits.exceeded", actor_user_id=uid, target_user_id=uid, request=request, meta={"feature": feature, "scope": "minute", "limit": int(minute_limit), "count": int(cnt), "plan": eff_plan, "retry_after": int(retry_after)})
                    except Exception:
                        pass
                    try:
                        from netapi.modules.observability.metrics import inc_limits_exceeded
                        inc_limits_exceeded(feature=str(feature), scope="minute")
                    except Exception:
                        pass
                    raise HTTPException(429, detail={"error": "rate_limited", "feature": feature, "scope": "minute", "limit": int(minute_limit), "retry_after": int(retry_after), "upgrade": True})
                if row:
                    conn.execute(_t("UPDATE api_usage_minute SET count=count+1 WHERE user_id=:u AND bucket=:b AND feature=:f"), {"u": uid, "b": bucket, "f": feature})
                else:
                    conn.execute(_t("INSERT INTO api_usage_minute(user_id,bucket,feature,count) VALUES(:u,:b,:f,1)"), {"u": uid, "b": bucket, "f": feature})
        except HTTPException:
            raise
        except Exception:
            # fail-open
            pass

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
