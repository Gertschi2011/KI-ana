from __future__ import annotations
import os, json, time, hmac, hashlib, base64
from typing import Any, Dict, Optional

# Lightweight HS256 JWT utils to avoid external deps

def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

def _b64url_decode(s: str) -> bytes:
    # restore padding
    pad = '=' * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))

def _secret() -> bytes:
    return os.getenv("KI_SECRET", "dev-insecure-change-me").encode("utf-8")

def encode_jwt(payload: Dict[str, Any], exp_seconds: int = 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    body = dict(payload)
    body.setdefault("iat", now)
    if exp_seconds:
        body.setdefault("exp", now + int(exp_seconds))
    head_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    body_b64 = _b64url_encode(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{head_b64}.{body_b64}".encode("utf-8")
    sig = hmac.new(_secret(), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{head_b64}.{body_b64}.{sig_b64}"

def decode_jwt(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        head_b64, body_b64, sig_b64 = parts
        signing_input = f"{head_b64}.{body_b64}".encode("utf-8")
        calc = hmac.new(_secret(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(calc, _b64url_decode(sig_b64)):
            return None
        payload = json.loads(_b64url_decode(body_b64).decode("utf-8"))
        exp = payload.get("exp")
        if isinstance(exp, (int, float)) and time.time() > float(exp):
            return None
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None

