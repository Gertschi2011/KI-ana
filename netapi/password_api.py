# netapi/password_api.py
# API-Router für Passwort-Reset & Token-Handling

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import secrets, os, json, pathlib, bcrypt, time

from .db import SessionLocal
from .models import User, EmailToken

router = APIRouter()

# --------- Helpers ---------

OUTBOX_DIR = "/home/kiana/ki_ana/netapi/outbox"
DOMAIN = os.getenv("KI_DOMAIN", "ki-ana.at")  # für Links in Mails

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _create_token(s: Session, user_id: int, purpose: str, ttl_seconds: int = 3600) -> str:
    # 43 Zeichen URL-sicher (≈ 256 Bit)
    token = secrets.token_urlsafe(32)
    et = EmailToken(
        token=token,
        user_id=user_id,
        purpose=purpose,
        created_at=_now_utc(),
        expires_at=_now_utc() + timedelta(seconds=ttl_seconds),
    )
    s.add(et)
    s.commit()
    return token

def _write_mail_file(recipient: str, subject: str, body: str):
    pathlib.Path(OUTBOX_DIR).mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fn = f"{OUTBOX_DIR}/{ts}_{recipient.replace('@','_')}.txt"
    with open(fn, "w", encoding="utf-8") as f:
        f.write(subject + "\n\n" + body)

# --------- Schemas ---------

class ForgotIn(BaseModel):
    identifier: str  # email ODER username

class ResetIn(BaseModel):
    token: str
    new_password: str

# --------- Endpoints ---------

@router.post("/api/forgot-password")
def forgot_password(payload: ForgotIn):
    """
    Nimmt email ODER username entgegen, erzeugt Reset-Token.
    Aus Sicherheitsgründen immer {ok:true} zurückgeben, egal ob User existiert.
    Token/Link landet in /home/kiana/ki_ana/netapi/outbox/*.txt (Debug-Mail).
    """
    ident = payload.identifier.strip()
    with SessionLocal() as s:
        # User lookup (username oder email)
        user = (
            s.query(User)
             .filter((User.username == ident) | (User.email == ident))
             .one_or_none()
        )

        # Immer ok antworten; Token nur erzeugen, wenn User existiert
        if user:
            tok = _create_token(s, user.id, purpose="reset", ttl_seconds=3600)
            reset_url = f"https://{DOMAIN}/static/reset.html?token={tok}"
            subject = "KI_ana – Passwort zurücksetzen"
            body = (
                f"Hallo {user.username},\n\n"
                f"hier ist dein Link zum Zurücksetzen des Passworts (gültig für 60 Min.):\n"
                f"{reset_url}\n\n"
                f"Wenn du das nicht warst, kannst du diese Nachricht ignorieren."
            )
            _write_mail_file(user.email or user.username, subject, body)

        return {"ok": True}


@router.post("/api/reset-password")
def reset_password(payload: ResetIn):
    """
    Setzt das Passwort über einen gültigen Token zurück.
    """
    token = payload.token.strip()
    new_pw = payload.new_password

    if len(new_pw) < 8:
        raise HTTPException(status_code=400, detail="password too short")

    with SessionLocal() as s:
        et = s.query(EmailToken).filter(
            EmailToken.token == token,
            EmailToken.purpose == "reset"
        ).one_or_none()

        if not et:
            raise HTTPException(status_code=400, detail="invalid token")

        # Ablauf prüfen
        if et.expires_at is not None:
            # expires_at kann als Text/DATETIME kommen; robust behandeln
            expires = et.expires_at
            if isinstance(expires, str):
                try:
                    expires = datetime.fromisoformat(expires)
                except Exception:
                    raise HTTPException(status_code=400, detail="invalid token time")

            if expires < _now_utc():
                # Token ist abgelaufen -> löschen
                s.delete(et)
                s.commit()
                raise HTTPException(status_code=400, detail="token expired")

        user = s.query(User).filter(User.id == et.user_id).one_or_none()
        if not user:
            # Token aufräumen, falls User nicht existiert
            s.delete(et)
            s.commit()
            raise HTTPException(status_code=400, detail="invalid token")

        # Passwort setzen (bcrypt)
        user.password_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
        user.updated_at = int(time.time())
        # Token verbrauchen (löschen)
        s.delete(et)
        s.commit()

        return {"ok": True}
