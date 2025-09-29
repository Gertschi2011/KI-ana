from __future__ import annotations
import time
import jwt
from dataclasses import dataclass
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from backend.core.config import Settings

ph = PasswordHasher()
settings = Settings()

@dataclass
class TokenPair:
    access: str
    refresh: str


def hash_password(raw: str) -> str:
    return ph.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        ph.verify(hashed, raw)
        return True
    except VerifyMismatchError:
        return False


def create_tokens(sub: str) -> TokenPair:
    now = int(time.time())
    access = jwt.encode({"sub": sub, "iat": now, "exp": now + 60*15}, settings.jwt_secret, algorithm="HS256")
    refresh = jwt.encode({"sub": sub, "iat": now, "exp": now + 60*60*24*7, "typ": "refresh"}, settings.jwt_secret, algorithm="HS256")
    return TokenPair(access=access, refresh=refresh)


def verify_token(token: str, refresh: bool = False) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if refresh and payload.get("typ") != "refresh":
            return None
        return payload
    except Exception:
        return None
