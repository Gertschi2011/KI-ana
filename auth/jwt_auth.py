import os, time
from typing import Optional, Tuple
from fastapi import Header, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ISSUER = "kiana"
JWT_TTL = int(os.getenv("JWT_TTL", "3600"))

def _ser():
    if not JWT_SECRET:
        return None
    return URLSafeTimedSerializer(JWT_SECRET, salt="kiana.jwt")

def issue_token(sub: str, role: str) -> str:
    s = _ser(); assert s
    return s.dumps({"sub": sub, "role": role, "iss": JWT_ISSUER, "iat": int(time.time())})

def verify_role(authorization: Optional[str], roles: Tuple[str, ...]) -> str:
    if not JWT_SECRET:
        return "public"
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer")
    token = authorization.split(" ", 1)[1]
    s = _ser(); assert s
    try:
        payload = s.loads(token, max_age=JWT_TTL)
        role = payload.get("role")
        if role not in roles:
            raise HTTPException(403, "role denied")
        return role
    except SignatureExpired:
        raise HTTPException(401, "token expired")
    except BadSignature:
        raise HTTPException(401, "bad token")

def require_worker(authorization: Optional[str] = Header(default=None)):
    return verify_role(authorization, ("worker", "admin"))

def require_admin(authorization: Optional[str] = Header(default=None)):
    return verify_role(authorization, ("admin",))
