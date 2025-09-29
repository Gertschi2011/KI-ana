from __future__ import annotations
import os
import hashlib
from backend.core.config import Settings

_settings = Settings()

SENTINEL_PATH = os.environ.get("EMERGENCY_SENTINEL", "/data/emergency_override")


def _file_hash(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            d = hashlib.sha256()
            for chunk in iter(lambda: f.read(8192), b""):
                d.update(chunk)
            return d.hexdigest()
    except Exception:
        return None


def emergency_active() -> bool:
    if not os.path.exists(SENTINEL_PATH):
        return False
    # If a hash is configured, validate match
    configured = (_settings.emergency_hash or "").strip()
    if not configured:
        return True
    actual = _file_hash(SENTINEL_PATH)
    return bool(actual and actual == configured)
