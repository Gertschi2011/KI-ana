# user_mgmt.py – Robustes User- & Session-Management für KI_ana
# - SQLite + SQLAlchemy
# - sichere Passwörter (bcrypt)
# - signierte Session-Cookies (itsdangerous)
# - JSON-APIs: /api/register, /api/login, /api/me, /api/logout
# - Form-Login: /auth/login
# - Rückwärtskompatible Tokens: issue_session_token / verify_session_token
# - Sanfte Migration fehlender Spalten (SQLite)

from __future__ import annotations

import os, time, typing as T
from datetime import datetime
from dataclasses import asdict, dataclass

from fastapi import APIRouter, Request, Response, HTTPException, status, Depends, Form
from fastapi.responses import JSONResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# Eigene Module
from .db import engine, SessionLocal
from .models import User, Base

# =========================
# Konfiguration / Utilities
# =========================
COOKIE_NAME = "ki_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 Tage
SESSION_TTL   = 60 * 60 * 24 * 30   # für Token-Verifikation (max. Alter)

def _secret_key() -> str:
    # 1) env bevorzugt
    k = os.getenv("KI_SECRET")
    if k: return k
    # 2) persistent unter ~/.config/ki_ana/secret.key
    cfg = os.path.expanduser("~/.config/ki_ana")
    os.makedirs(cfg, exist_ok=True)
    p = os.path.join(cfg, "secret.key")
    if not os.path.exists(p):
        import secrets
        with open(p, "w") as f:
            f.write(secrets.token_urlsafe(48))
    with open(p, "r") as f:
        return f.read().strip()

serializer = URLSafeTimedSerializer(_secret_key())

def _serialize_session(uid: int) -> str:
    return serializer.dumps({"uid": int(uid), "ts": int(time.time())})

def _deserialize_session(token: str) -> int | None:
    try:
        data = serializer.loads(token, max_age=SESSION_TTL)
        return int(data.get("uid", 0)) or None
    except (BadSignature, SignatureExpired):
        return None

def _set_session_cookie(response: Response, token: str, request: Request | None = None) -> None:
    secure = True
    # Lokale Tests über http://127.0.0.1 nicht „secure“ erzwingen
    if request is not None and (request.url.hostname in ("127.0.0.1", "localhost")):
        secure = False
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )

def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")

# =========================
# DB: Init & Migration
# =========================
def init_db() -> None:
    """Create tables + fehlende Spalten sanft ergänzen (nur ADD COLUMN)."""
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info('users')")}
        # gewünschte Spalten (falls bei alten DBs fehlen)
        add_stmt: list[str] = []
        if "plan" not in cols:
            add_stmt.append("ALTER TABLE users ADD COLUMN plan TEXT DEFAULT 'free'")
        if "plan_until" not in cols:
            add_stmt.append("ALTER TABLE users ADD COLUMN plan_until INTEGER DEFAULT 0")
        if "birthdate" not in cols:
            add_stmt.append("ALTER TABLE users ADD COLUMN birthdate TEXT DEFAULT ''")
        if "address" not in cols:
            add_stmt.append("ALTER TABLE users ADD COLUMN address TEXT DEFAULT ''")
        if "created_at" not in cols:
            add_stmt.append("ALTER TABLE users ADD COLUMN created_at INTEGER DEFAULT 0")
        if "updated_at" not in cols:
            add_stmt.append("ALTER TABLE users ADD COLUMN updated_at INTEGER DEFAULT 0")
        for stmt in add_stmt:
            conn.exec_driver_sql(stmt)

# user_mgmt.py – Sessions, Auth, Passwort-Reset Helfer
import os, time, secrets
from datetime import datetime, timedelta
import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from sqlalchemy import create_engine, select, update, delete
from sqlalchemy.orm import sessionmaker

from .models import Base, User, EmailToken

DB_PATH = f"sqlite:////home/kiana/ki_ana/netapi/users.db"
engine = create_engine(DB_PATH, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def init_db():
    Base.metadata.create_all(engine)

# === Passwort-Hashing ===
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), h.encode("utf-8"))
    except Exception:
        return False

# === Users ===
def get_user_by_id(user_id: int):
    with SessionLocal() as s:
        return s.get(User, int(user_id))

def get_user_by_username(username: str):
    with SessionLocal() as s:
        q = s.execute(select(User).where(User.username == username)).scalars().first()
        return q

def get_user_by_email(email: str):
    with SessionLocal() as s:
        return s.execute(select(User).where(User.email == email)).scalars().first()

def set_user_password(user_id: int, new_password: str):
    new_hash = hash_password(new_password)
    with SessionLocal() as s:
        s.execute(
            update(User)
            .where(User.id == int(user_id))
            .values(password_hash=new_hash, updated_at=datetime.utcnow())
        )
        s.commit()

# === Sessions (Cookie) ===
def _secret() -> str:
    return os.getenv("KI_SECRET", "dev-insecure-change-me")

def _signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret(), salt="ki_session")

def issue_session_token(user_id: int) -> str:
    s = _signer()
    return s.dumps({"uid": int(user_id), "ts": int(time.time())})

def verify_session_token(token: str):
    s = _signer()
    try:
        return s.loads(token, max_age=60 * 60 * 24 * 30)  # 30 Tage
    except (BadSignature, SignatureExpired):
        return None

# === Passwort-Reset ===
def create_reset_token_for_email(email: str, ttl_minutes: int = 30) -> str | None:
    """Gibt den Token-String zurück (für DEV/Creator zeigen wir ihn im API-Response)."""
    u = get_user_by_email(email)
    if not u:
        return None
    token = secrets.token_urlsafe(48)  # raw token
    expires = datetime.utcnow() + timedelta(minutes=ttl_minutes)
    with SessionLocal() as s:
        s.add(EmailToken(token=token, user_id=u.id, purpose="reset",
                         created_at=datetime.utcnow(), expires_at=expires))
        s.commit()
    return token

def verify_reset_token(token: str) -> User | None:
    now = datetime.utcnow()
    with SessionLocal() as s:
        et = s.get(EmailToken, token)
        if not et or et.purpose != "reset" or et.expires_at < now:
            return None
        user = s.get(User, et.user_id)
        return user

def consume_reset_token(token: str):
    with SessionLocal() as s:
        s.execute(delete(EmailToken).where(EmailToken.token == token))
        s.commit()

# ================
# Passwort-Utility
# ================
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False

# ===========
# CRUD / Auth
# ===========
def create_user(
    s: Session,
    *,
    username: str,
    email: str,
    password: str,
    role: str = "user",
    plan: str = "free",
    plan_until: int = 0,
    birthdate: str = "",
    address: str = "",
) -> User:
    now = int(time.time())
    u = User(
        username=username.strip(),
        email=email.strip(),
        role=role,
        password_hash=hash_password(password),
        plan=plan,
        plan_until=plan_until,
        birthdate=birthdate,
        address=address,
        created_at=now,
        updated_at=now,
    )
    s.add(u)
    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        raise HTTPException(status_code=409, detail="username or email already exists")
    s.refresh(u)
    return u

def get_user_by_username(s: Session, username: str) -> User | None:
    return s.scalar(select(User).where(User.username == username))

def get_user_by_id(s: Session, user_id: int) -> User | None:
    return s.scalar(select(User).where(User.id == int(user_id)))

def authenticate(s: Session, username: str, password: str) -> User | None:
    u = get_user_by_username(s, username)
    if not u:
        return None
    if not verify_password(password, u.password_hash):
        return None
    return u

# Rückwärtskompatible Token-Funktionen (einige alte app.py haben diese Imports)
def issue_session_token(user_id: int) -> str:
    return _serialize_session(user_id)

def verify_session_token(token: str) -> int | None:
    return _deserialize_session(token)

# „Public“ Helper für app.py & andere Router
def get_user_from_request(request: Request) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    uid = _deserialize_session(token)
    if not uid:
        return None
    with SessionLocal() as s:
        return get_user_by_id(s, uid)

# Alias (für ältere app.py, die _get_user_from_cookie nennen)
_get_user_from_cookie = get_user_from_request

# =======================
# Pydantic Request Models
# =======================
from pydantic import BaseModel, EmailStr, Field

class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=6)
    birthdate: str = ""
    address: str = ""

class LoginIn(BaseModel):
    username: str
    password: str

# ================
# API-Router / JSON
# ================
auth_router = APIRouter(prefix="/api", tags=["auth"])

@auth_router.post("/register")
def api_register(inp: RegisterIn, request: Request):
    with SessionLocal() as s:
        u = create_user(
            s,
            username=inp.username,
            email=inp.email,
            password=inp.password,
            role="user",
            birthdate=inp.birthdate,
            address=inp.address,
        )
        token = _serialize_session(u.id)
        resp = JSONResponse({
            "ok": True,
            "user": {
                "id": u.id, "username": u.username, "role": u.role,
                "plan": u.plan, "plan_until": u.plan_until
            }
        })
        _set_session_cookie(resp, token, request)
        return resp

@auth_router.post("/login")
def api_login(inp: LoginIn, request: Request):
    with SessionLocal() as s:
        u = authenticate(s, inp.username, inp.password)
        if not u:
            raise HTTPException(status_code=401, detail="invalid credentials")
        token = _serialize_session(u.id)
        resp = JSONResponse({
            "ok": True,
            "user": {
                "id": u.id, "username": u.username, "role": u.role,
                "plan": u.plan, "plan_until": u.plan_until
            }
        })
        _set_session_cookie(resp, token, request)
        return resp

@auth_router.get("/me")
def api_me(request: Request):
    u = get_user_from_request(request)
    if not u:
        return {"auth": False}
    # derive roles list from role string and is_papa flag
    role_str = (u.role or "").strip()
    roles = [r.strip() for r in role_str.split(',') if r.strip()] if role_str else []
    if getattr(u, 'is_papa', False) and 'papa' not in roles:
        roles.append('papa')
    return {
        "auth": True,
        "user": {
            "id": u.id,
            "username": u.username,
            "role": role_str,
            "roles": roles,
            "is_papa": bool(getattr(u, 'is_papa', False)),
            "plan": u.plan,
            "plan_until": u.plan_until
        }
    }

@auth_router.post("/logout")
def api_logout():
    resp = JSONResponse({"ok": True})
    _clear_session_cookie(resp)
    return resp

# ==================
# /auth – Form-Login
# ==================
form_router = APIRouter(prefix="/auth", tags=["auth"])

@form_router.post("/login")
def form_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    with SessionLocal() as s:
        u = authenticate(s, username, password)
        if not u:
            raise HTTPException(status_code=401, detail="invalid credentials")
        token = _serialize_session(u.id)
        resp = JSONResponse({
            "ok": True,
            "user": {
                "id": u.id, "username": u.username, "role": u.role,
                "plan": u.plan, "plan_until": u.plan_until
            }
        })
        _set_session_cookie(resp, token, request)
        return resp

@form_router.get("/me")
def form_me(request: Request):
    u = get_user_from_request(request)
    if not u:
        return {"auth": False}
    return {"auth": True, "username": u.username, "role": u.role}

# =============
# Router Export
# =============
# Damit app.py diese sauber einbinden kann:
#  - auth_router:   /api/*
#  - form_router:   /auth/*
routers = (auth_router, form_router)

# Beim Import die DB sicher initialisieren
init_db()
