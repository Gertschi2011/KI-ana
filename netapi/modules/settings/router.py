from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional, List
from pathlib import Path
import json, os

from ...deps import get_current_user_required
from ...config import settings as app_settings, PROJECT_ROOT
from ...db import SessionLocal
from ...models import SettingsKV
# Reuse Sub‑KI registration dir if the module is present; be resilient otherwise
try:
    from ...modules.subki.router import REG_DIR  # type: ignore
except Exception:
    # Fallback to conventional path to avoid import‑time failure breaking this router
    REG_DIR = (PROJECT_ROOT / "subki" / "registrations")

router = APIRouter(prefix="/api/settings", tags=["settings"])

RUNTIME_DIR = PROJECT_ROOT / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_JSON = RUNTIME_DIR / "settings.json"
DOT_ENV = PROJECT_ROOT / ".env"


def _load_db_settings() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        with SessionLocal() as db:
            rows = db.query(SettingsKV).all()
            for r in rows:
                out[str(r.key)] = r.value
    except Exception:
        out = {}
    return out


def _save_db_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    try:
        with SessionLocal() as db:
            for k, v in (updates or {}).items():
                k2 = str(k)
                val = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
                row = db.query(SettingsKV).filter(SettingsKV.key == k2).first()
                if row:
                    row.value = val
                else:
                    db.add(SettingsKV(key=k2, value=val))
            db.commit()
        # return merged
        cur = _load_db_settings()
        cur.update(updates or {})
        return cur
    except Exception as e:
        raise HTTPException(500, f"settings_persist_error: {e}")


def _read_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not DOT_ENV.exists():
        return env
    for line in DOT_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()
    return env


def _write_env(updates: Dict[str, str]) -> None:
    """Best-effort .env updater: updates existing keys or appends new ones."""
    try:
        env = _read_env()
        env.update({k: str(v) for k, v in (updates or {}).items()})
        lines = [f"{k}={v}" for k, v in env.items()]
        DOT_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        # Non-fatal: keep runtime JSON as the source of truth
        pass


def _is_admin(user: Dict[str, Any]) -> bool:
    role = str(user.get("role") or "").lower()
    roles = set([role] + [str(r).lower() for r in (user.get("roles") or [])])
    return "admin" in roles


@router.get("")
def get_settings(user = Depends(get_current_user_required)) -> Dict[str, Any]:
    # Base from DB
    data = _load_db_settings()
    # Normalize parse JSON-like strings
    def _parse(v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return v
        return v
    data = {k: _parse(v) for k, v in data.items()}
    # Merge with defaults
    merged: Dict[str, Any] = {
        "theme": (data.get("theme") or "system"),
        "language": data.get("language") or os.getenv("KI_LANG_DEFAULT", "de-DE"),
        "memory_on": int(str(data.get("memory_on") or "1") in {"1","true","True"}),
        "autopilot_on": int(str(data.get("autopilot_on") or "1") in {"1","true","True"}),
        # legacy/extended fields for backward compatibility
        "ethics_filter": data.get("ethics_filter") or os.getenv("KI_ETHICS_FILTER", "default"),
        "active_subkis": data.get("active_subkis") or [],
        "allow_net": bool(data.get("allow_net", getattr(app_settings, "ALLOW_NET", True))),
        "ollama_host": getattr(app_settings, "OLLAMA_HOST", None),
        "ollama_model": getattr(app_settings, "OLLAMA_MODEL", None),
    }
    # Discover available Sub-KIs from registrations
    available: list[str] = []
    try:
        for p in REG_DIR.glob("*.json"):
            available.append(p.stem)
    except Exception:
        available = []
    return {"ok": True, "settings": merged, "available_subkis": available}


from pydantic import BaseModel

class SettingsIn(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    memory_on: Optional[int] = None
    autopilot_on: Optional[int] = None
    ethics_filter: Optional[str] = None
    active_subkis: Optional[List[str]] = None
    allow_net: Optional[bool] = None


@router.post("")
def update_settings(payload: SettingsIn, user = Depends(get_current_user_required)) -> Dict[str, Any]:
    # Any authenticated user can update basic preferences
    body = (payload.model_dump(exclude_none=True) if isinstance(payload, SettingsIn) else dict(payload or {}))
    # Accept only known keys
    allowed = {"theme", "language", "memory_on", "autopilot_on", "ethics_filter", "active_subkis", "allow_net"}
    for k in list(body.keys()):
        if k not in allowed:
            body.pop(k, None)
    # Normalize booleans for *_on fields (store 0/1)
    if "memory_on" in body:
        body["memory_on"] = 1 if str(body["memory_on"]) in {"1","true","True"} else 0
    if "autopilot_on" in body:
        body["autopilot_on"] = 1 if str(body["autopilot_on"]) in {"1","true","True"} else 0
    # Validate active_subkis
    if "active_subkis" in body:
        vals = body.get("active_subkis")
        if not isinstance(vals, list):
            raise HTTPException(400, "active_subkis must be a list")
        reg = [p.stem for p in REG_DIR.glob("*.json")] if REG_DIR.exists() else []
        body["active_subkis"] = [s for s in vals if isinstance(s, str) and s in reg]
    # Persist to DB
    data = _save_db_settings(body)
    # Mirror into .env when applicable (best-effort)
    updates: Dict[str, str] = {}
    if "theme" in body:
        updates["KI_THEME_DEFAULT"] = str(body["theme"])
    if "language" in body:
        updates["KI_LANG_DEFAULT"] = str(body["language"])  # consumer can read this
    if "ethics_filter" in body:
        updates["KI_ETHICS_FILTER"] = str(body["ethics_filter"])  # e.g., default/strict/off
    if "allow_net" in body:
        updates["ALLOW_NET"] = "1" if bool(body["allow_net"]) else "0"
    if updates:
        _write_env(updates)
    # Return merged settings including defaults
    return get_settings(user)
