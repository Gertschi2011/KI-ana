from __future__ import annotations

import os
import time
import hmac
import json
import base64
import smtplib
import secrets
import datetime as dt
from typing import Optional, Tuple

from fastapi import APIRouter, Request, Response, HTTPException, status, Body
from pydantic import BaseModel, EmailStr, Field
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text, ForeignKey,
    UniqueConstraint, create_engine, select, func
)
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import bcrypt

# ======================================================================================
# Konfiguration
# ======================================================================================

# DB-URL (Default: SQLite im Netapi-Verzeichnis)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DB_URL = os.environ.get("KIANA_DB_URL", f"sqlite:///{os.path.join(_THIS_DIR, 'users.db')}")

# Cookie-Einstellungen
COOKIE_NAME  = os.environ.get("KIANA_COOKIE_NAME", "ki_session")
COOKIE_DOMAIN= os.environ.get("KIANA_COOKIE_DOMAIN", None)   # z.B. "ki-ana.at" (None = automatisch)
COOKIE_SECURE= os.environ.get("KIANA_COOKIE_SECURE", "1") in ("1","true","True")
COOKIE_SAMESITE = os.environ.get("KIANA_COOKIE_SAMESITE", "Lax")
SESSION_TTL_DAYS = int(os.environ.get("KIANA_SESSION_TTL_DAYS", "7"))

# SMTP (optional). Wenn nicht gesetzt: wir "mailen" in den Logs.
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "no-reply@localhost")

# Admin-Bootstrap
ADMIN_USER = os.environ.get("KIANA_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("KIANA_ADMIN_PASS", "ChangeMe!123")
ADMIN_EMAIL= os.environ.get("KIANA_ADMIN_EMAIL","admin@example.com")

# ======================================================================================
# DB-Setup & Modelle
# ======================================================================================

Base = declarative_base()
engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_user_username"),
        UniqueConstraint("email",    name="uq_user_email"),
    )

    id           = Column(Integer, primary_key=True)
    username     = Column(String(80), nullable=False)
    email        = Column(String(255), nullable=False)
    password_hash= Column(String(255), nullable=False)
    role         = Column(String(20),  default="user")     # user | creator | admin
    plan         = Column(String(20),  default="free")     # free | plus | pro
    plan_until   = Column(DateTime,    nullable=True)
    email_verified = Column(Boolean,   default=False)
    created_at   = Column(DateTime,    default=func.now())
    updated_at   = Column(DateTime,    default=func.now(), onupdate=func.now())

    sessions     = relationship("Session", back_populates="user", cascade="all,delete-orphan")

    # Passwörter
    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def check_password(self, password: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))
        except Exception:
            return False

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "plan": self.plan,
            "plan_until": int(self.plan_until.timestamp()) if self.plan_until else 0,
            "email_verified": self.email_verified,
        }

class Session(Base):
    __tablename__ = "sessions"

    token       = Column(String(128), primary_key=True)  # zufälliges Token (Base64URL)
    user_id     = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    created_at  = Column(DateTime, default=func.now())
    expires_at  = Column(DateTime, nullable=False)
    ip          = Column(String(64), default="")
    user_agent  = Column(Text, default="")

    user        = relationship("User", back_populates="sessions")

class EmailToken(Base):
    __tablename__ = "email_tokens"

    token       = Column(String(128), primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    purpose     = Column(String(20), nullable=False)  # verify | reset
    created_at  = Column(DateTime, default=func.now())
    expires_at  = Column(DateTime, nullable=False)

# Tabellen anlegen
Base.metadata.create_all(engine)

# ======================================================================================
# Utility
# ======================================================================================

def _now() -> dt.datetime:
    return dt.datetime.utcnow()

def _gen_token(nbytes: int = 32) -> str:
    # Base64URL ohne '='
    return base64.urlsafe_b64encode(secrets.token_bytes(nbytes)).decode().rstrip("=")

def _cookie_domain_from_host(host: str) -> Optional[str]:
    # Host kann "ki-ana.at:443" sein → Domain extrahieren
    if not host:
        return None
    d = host.split(":")[0]
    # für localhost/127.* kein Domain-Attribut setzen
    if d in ("localhost", "127.0.0.1"):
        return None
    return d

def send_email(to: str, subject: str, body: str) -> None:
    """Einfache Mail. Fällt auf Logging zurück, wenn SMTP nicht konfiguriert."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and MAIL_FROM):
        print(f"[MAIL-LOG] To: {to}\nSubject: {subject}\n\n{body}\n---")
        return
    msg = f"From: {MAIL_FROM}\r\nTo: {to}\r\nSubject: {subject}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body}"
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(MAIL_FROM, [to], msg.encode("utf-8"))

def init_db() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        # Admin-Bootstrap: wenn keine User existieren
        existing = db.scalar(select(func.count(User.id)))
        if not existing:
            admin = User(username=ADMIN_USER, email=ADMIN_EMAIL, role="admin", plan="pro")
            admin.set_password(ADMIN_PASS)
            # 180 Tage Pro
            admin.plan_until = _now() + dt.timedelta(days=180)
            admin.email_verified = True
            db.add(admin)
            db.commit()
            print(f"[BOOTSTRAP] Admin '{ADMIN_USER}' angelegt (Passwort aus KIANA_ADMIN_PASS).")

# ======================================================================================
# Sessions / Tokens
# ======================================================================================

def issue_session(db, user: User, ip: str = "", user_agent: str = "") -> str:
    token = _gen_token(32)
    expires = _now() + dt.timedelta(days=SESSION_TTL_DAYS)
    s = Session(token=token, user_id=user.id, expires_at=expires, ip=ip, user_agent=user_agent)
    db.add(s)
    db.commit()
    return token

def get_user_by_session(db, token: str) -> Optional[User]:
    if not token:
        return None
    s = db.get(Session, token)
    if not s:
        return None
    if s.expires_at < _now():
        # abgelaufen → löschen
        db.delete(s)
        db.commit()
        return None
    return db.get(User, s.user_id)

def revoke_session(db, token: str) -> None:
    s = db.get(Session, token)
    if s:
        db.delete(s)
        db.commit()

def create_user(
    db,
    *,
    username: str,
    email: str,
    password: str,
    role: str = "user",
    plan: str = "free",
    plan_days: int = 0
) -> User:
    # Duplikate abfangen
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=400, detail="Username bereits vergeben")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=400, detail="Email bereits vergeben")

    u = User(username=username, email=email, role=role, plan=plan)
    u.set_password(password)
    if plan_days > 0:
        u.plan_until = _now() + dt.timedelta(days=plan_days)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

def authenticate(db, username: str, password: str) -> Optional[User]:
    u = db.scalar(select(User).where(User.username == username))
    if not u:
        return None
    if not u.check_password(password):
        return None
    return u

def issue_email_token(db, user: User, purpose: str, ttl_hours: int = 2) -> str:
    t = _gen_token(24)
    tok = EmailToken(
        token=t, user_id=user.id, purpose=purpose,
        expires_at=_now() + dt.timedelta(hours=ttl_hours)
    )
    db.add(tok)
    db.commit()
    return t

def use_email_token(db, token: str, expected_purpose: str) -> Optional[User]:
    tok = db.get(EmailToken, token)
    if not tok or tok.purpose != expected_purpose or tok.expires_at < _now():
        return None
    u = db.get(User, tok.user_id)
    db.delete(tok)
    db.commit()
    return u

# ======================================================================================
# Pydantic IO
# ======================================================================================

class RegisterIn(BaseModel):
    username: str = Field(min_length=3)
    email: EmailStr
    password: str = Field(min_length=6)

class LoginIn(BaseModel):
    username: str
    password: str
    remember: bool = False

class ResetRequestIn(BaseModel):
    email_or_username: str

class ResetConfirmIn(BaseModel):
    token: str
    new_password: str = Field(min_length=6)

# ======================================================================================
# FastAPI Router
# ======================================================================================

router = APIRouter()

def _set_session_cookie(resp: Response, request: Request, token: str, remember: bool) -> None:
    max_age = SESSION_TTL_DAYS * 24 * 60 * 60 if remember else None
    domain = COOKIE_DOMAIN or _cookie_domain_from_host(request.headers.get("host",""))
    resp.set_cookie(
        COOKIE_NAME, token,
        path="/",
        max_age=max_age,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=domain
    )

def _clear_session_cookie(resp: Response, request: Request) -> None:
    domain = COOKIE_DOMAIN or _cookie_domain_from_host(request.headers.get("host",""))
    resp.delete_cookie(COOKIE_NAME, path="/", domain=domain, samesite=COOKIE_SAMESITE)

def _get_session_token_from_request(request: Request) -> str:
    # Cookie bevorzugt, sonst Authorization: Bearer <token>
    token = request.cookies.get(COOKIE_NAME) or ""
    if not token:
        auth = request.headers.get("authorization","")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ",1)[1].strip()
    return token

@router.post("/api/register")
def api_register(payload: RegisterIn, request: Request):
    with SessionLocal() as db:
        u = create_user(db,
                        username=payload.username,
                        email=payload.email,
                        password=payload.password,
                        role="user",
                        plan="free",
                        plan_days=0)
        # E-Mail-Verifikation (Token mailen / loggen)
        token = issue_email_token(db, u, "verify", ttl_hours=24)
        verify_url = f"https://{request.headers.get('host','')}/auth/verify?token={token}"
        send_email(u.email, "Bitte E-Mail verifizieren",
                   f"Hallo {u.username},\n\nbitte bestätige deine E-Mail:\n{verify_url}\n\nDanke!")
        return {"ok": True, "user": u.to_public()}

@router.get("/auth/verify")
def auth_verify(token: str):
    with SessionLocal() as db:
        u = use_email_token(db, token, "verify")
        if not u:
            raise HTTPException(status_code=400, detail="Token ungültig oder abgelaufen")
        u.email_verified = True
        db.commit()
        return {"ok": True, "message": "E-Mail bestätigt."}

@router.post("/api/login")
def api_login(payload: LoginIn, request: Request, response: Response):
    with SessionLocal() as db:
        u = authenticate(db, payload.username, payload.password)
        if not u:
            raise HTTPException(status_code=401, detail="invalid credentials")
        token = issue_session(db, u, ip=request.client.host if request.client else "", user_agent=request.headers.get("user-agent",""))
        _set_session_cookie(response, request, token, remember=payload.remember)
        return {"ok": True, "token": token, "user": u.to_public()}

# optional: Form-Login (für HTML-Formulare)
@router.post("/auth/login")
def auth_login_form(request: Request, response: Response,
                    username: str = Body(..., embed=True),
                    password: str = Body(..., embed=True),
                    remember: bool = Body(False, embed=True)):
    with SessionLocal() as db:
        u = authenticate(db, username, password)
        if not u:
            raise HTTPException(status_code=401, detail="invalid credentials")
        token = issue_session(db, u, ip=request.client.host if request.client else "", user_agent=request.headers.get("user-agent",""))
        _set_session_cookie(response, request, token, remember=remember)
        return {"ok": True, "token": token, "user": u.to_public()}

# /api/me und /auth/me liefern dasselbe, damit Nav/Chat flexibel sind
@router.get("/api/me")
@router.get("/auth/me")
def api_me(request: Request):
    token = _get_session_token_from_request(request)
    with SessionLocal() as db:
        u = get_user_by_session(db, token)
        if not u:
            return {"auth": False}
        return {"auth": True, "user": u.to_public()}

@router.post("/auth/logout")
def auth_logout(request: Request, response: Response):
    token = _get_session_token_from_request(request)
    with SessionLocal() as db:
        if token:
            revoke_session(db, token)
    _clear_session_cookie(response, request)
    return {"ok": True}

# Passwort-Reset
@router.post("/auth/reset/request")
def reset_request(payload: ResetRequestIn, request: Request):
    with SessionLocal() as db:
        u = db.scalar(
            select(User).where(
                (User.email == payload.email_or_username) | (User.username == payload.email_or_username)
            )
        )
        # Immer 200 antworten (keine User-Aufdeckung)
        if u:
            token = issue_email_token(db, u, "reset", ttl_hours=2)
            url = f"https://{request.headers.get('host','')}/auth/reset?token={token}"
            send_email(u.email, "Passwort zurücksetzen", f"Hallo {u.username},\n\nPasswort neu setzen:\n{url}\n\n(2h gültig)")
        return {"ok": True}

@router.post("/auth/reset/confirm")
def reset_confirm(payload: ResetConfirmIn):
    with SessionLocal() as db:
        u = use_email_token(db, payload.token, "reset")
        if not u:
            raise HTTPException(status_code=400, detail="Token ungültig oder abgelaufen")
        u.set_password(payload.new_password)
        db.commit()
        return {"ok": True, "message": "Passwort aktualisiert."}

# ======================================================================================
# Public Helpers für app.py
# ======================================================================================

def require_user(request: Request) -> User:
    token = _get_session_token_from_request(request)
    with SessionLocal() as db:
        u = get_user_by_session(db, token)
        if not u:
            raise HTTPException(status_code=401, detail="login required")
        return u

def current_user_optional(request: Request) -> Optional[User]:
    token = _get_session_token_from_request(request)
    with SessionLocal() as db:
        return get_user_by_session(db, token)

def get_user_by_id(user_id: int) -> Optional[User]:
    with SessionLocal() as db:
        return db.get(User, user_id)

# Beim Import einmal sicherstellen:
init_db()

def _load_secret_key():
    import pathlib
    env = os.getenv("KI_SECRET")
    if env:
        return env
    cfg_dir = os.path.expanduser("~/.config/ki_ana")
    os.makedirs(cfg_dir, exist_ok=True)
    key_path = os.path.join(cfg_dir, "secret.key")
    if os.path.exists(key_path):
        return open(key_path).read().strip()
    key = secrets.token_urlsafe(48)
    with open(key_path,"w") as f: f.write(key)
    return key

def _serializer():
    return URLSafeTimedSerializer(_load_secret_key(), salt="ki_ana.session.v1")

def issue_session_token(user_id:int)->str:
    s = _serializer()
    return s.dumps({"uid":int(user_id),"ts":int(time.time())})

def verify_session_token(token:str, max_age:int=60*60*24*7)->int|None:
    if not token: return None
    s=_serializer()
    try:
        data=s.loads(token,max_age=max_age)
        return int(data.get("uid"))
    except Exception: return None
