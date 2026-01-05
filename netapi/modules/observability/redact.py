from __future__ import annotations

from typing import Any


_REDACT_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "secret",
    "stripe_signature",
}


def _redact_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        # Keep shape but hide secrets
        if len(value) <= 8:
            return "[redacted]"
        return value[:2] + "…" + value[-2:]
    return "[redacted]"


def redact(obj: Any) -> Any:
    """Best-effort redaction for logs/metrics payloads."""
    try:
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for k, v in obj.items():
                key = str(k).lower()
                if key in _REDACT_KEYS:
                    out[k] = _redact_value(v)
                else:
                    out[k] = redact(v)
            return out
        if isinstance(obj, (list, tuple)):
            return [redact(x) for x in obj]
        return obj
    except Exception:
        return obj
