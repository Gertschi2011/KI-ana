from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
from typing import Dict, Any
import json, hashlib, os

from ...deps import get_current_user_required, require_role

router = APIRouter(prefix="/api/guardian", tags=["guardian"])

KI_ROOT = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))).resolve()
SYS = KI_ROOT / "system"


def _read_json(p: Path) -> Dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _sha256_canonical(obj: Dict[str, Any]) -> str:
    try:
        raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
    except Exception:
        return ""


def _check_secure_pair(name: str) -> Dict[str, Any]:
    j = SYS / f"{name}.json"
    h = SYS / f"{name}.hash"
    exists = j.exists()
    obj = _read_json(j) if exists else {}
    calc = _sha256_canonical(obj) if exists else ""
    stored = (h.read_text().strip() if h.exists() else "")
    ok = bool(exists and stored and calc and stored == calc)
    return {"name": name, "exists": exists, "hash_ok": ok, "hash_calc": calc, "hash_stored": stored}


@router.get("/status")
def guardian_status(user = Depends(get_current_user_required)):
    # Visible for creator/admin/papa
    # We accept role 'papa' in the comma-separated role string as well
    roles = set((str(user.get('role') or '')).lower().replace(',', ' ').split())
    allowed = False
    try:
        # require_role returns or raises; treat return as allowed
        require_role(user, {"creator","admin"})
        allowed = True
    except Exception:
        allowed = False
    if not (allowed or ("papa" in roles) or bool(user.get("is_papa"))):
        raise HTTPException(403, "forbidden")
    items = [
        _check_secure_pair("emergency_override"),
        _check_secure_pair("access_control"),
        _check_secure_pair("chain_validator"),
    ]
    # Report current emergency stop state
    sent = KI_ROOT / "emergency_stop"
    active = sent.exists()
    details: Dict[str, Any] = {}
    if active:
        try:
            details = json.loads(sent.read_text(encoding="utf-8"))
        except Exception:
            details = {"file": str(sent)}
    return {"ok": True, "items": items, "emergency_active": active, "emergency_details": details}
