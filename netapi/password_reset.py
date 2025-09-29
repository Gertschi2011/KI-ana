# netapi/password_reset.py
# Robust: Tokens, Rate-Limit, Outbox-Datei (für Mail-Weiterleitung), Passwort-Setzen

import os, time, json, secrets, bcrypt
from pathlib import Path
from typing import Optional, Tuple
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from .db import SessionLocal
from .models import User
from sqlalchemy import select

# -------------------- Secret / Serializer --------------------
def _secret_path() -> Path:
    return Path.home() / ".config" / "ki_ana" / "secret.key"

def get_secret() -> str:
    env = os.getenv("KI_SECRET")
    if env:
        return env
    p = _secret_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return p.read_text(encoding="utf-8").strip()

def get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_secret())

# -------------------- Rate Limiting (einfach & robust) --------------------
_RATE_FILE = Path(__file__).resolve().parent / "password_reset_rate.json"

def _rate_load() -> dict:
    try:
        return json.loads(_RATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _rate_save(d: dict) -> None:
    try:
        _RATE_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def rate_allow(key: str, limit: int = 3, per_seconds: int = 3600) -> bool:
    now = int(time.time())
    data = _rate_load()
    hits = [t for t in data.get(key, []) if now - t < per_seconds]
    if len(hits) >= limit:
        return False
    hits.append(now)
    data[key] = hits
    _rate_save(data)
    return True

# -------------------- Outbox (Mail-Ersatz) --------------------
def outbox_paths() -> Tuple[Path, Path]:
    base = Path(__file__).resolve().parent / "static"
    base.mkdir(parents=True, exist_ok=True)
    return base / "_reset_outbox.txt", base / "_reset_last_token.txt"

def outbox_write(recipient: str, token: str) -> None:
    outbox, last = outbox_paths()
    msg = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] reset for {recipient}: {token}\n"
    try:
        with outbox.open("a", encoding="utf-8") as f:
            f.write(msg)
        last.write_text(token, encoding="utf-8")
    except Exception:
        pass

# -------------------- User helpers --------------------
def find_user(identifier: str, session) -> Optional[User]:
    if "@" in identifier:
        return session.scalar(select(User).where(User.email == identifier))
    return session.scalar(select(User).where(User.username == identifier))

def set_user_password(user_id: int, new_password: str) -> bool:
    pw_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    with SessionLocal() as s:
        u = s.scalar(select(User).where(User.id == int(user_id)))
        if not u:
            return False
        u.password_hash = pw_hash
        # versuche optionale Spalten nicht anzutasten – reine PW-Änderung
        s.commit()
        return True

# -------------------- Tokens --------------------
_SALT = "ki_ana_pwd_reset"

def issue_reset_token(user_id: int) -> str:
    s = get_serializer()
    payload = {"uid": int(user_id), "ts": int(time.time())}
    return s.dumps(payload, salt=_SALT)

def verify_reset_token(token: str, max_age: int = 7200) -> Optional[int]:
    s = get_serializer()
    try:
        obj = s.loads(token, salt=_SALT, max_age=max_age)
        return int(obj.get("uid"))
    except (BadSignature, SignatureExpired, Exception):
        return None
