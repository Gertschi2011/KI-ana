from __future__ import annotations
from fastapi import APIRouter, Header, HTTPException, Body
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import Any, Dict, List, Optional
import json, time, uuid
from importlib.machinery import SourceFileLoader

router = APIRouter(prefix="/persona", tags=["persona"]) 

BASE_DIR = Path.home() / "ki_ana"
DATA_DIR = BASE_DIR / "persona"
REGISTRY = DATA_DIR / "registry.json"
BLOCK_UTILS_PATH = BASE_DIR / "system" / "block_utils.py"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_registry() -> Dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not REGISTRY.exists():
        return {"personas": {}}
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return {"personas": {}}


def _save_registry(data: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _load_block_utils():
    return SourceFileLoader("block_utils", str(BLOCK_UTILS_PATH)).load_module()  # type: ignore


@router.post("/register")
async def persona_register(name: Optional[str] = Body(None, embed=True)):
    reg = _load_registry()
    pid = str(uuid.uuid4())
    token = str(uuid.uuid4()).replace("-", "")
    reg["personas"].setdefault(pid, {
        "name": name or f"persona-{pid[:8]}",
        "token": token,
        "created_at": _now_iso(),
        "last_sync": None,
        "blocks": 0,
    })
    _save_registry(reg)
    return {"ok": True, "id": pid, "token": token}


@router.get("/status")
async def persona_status(x_persona_token: Optional[str] = Header(None)):
    reg = _load_registry()
    # if token provided, return only that persona's status
    if x_persona_token:
        for pid, rec in reg.get("personas", {}).items():
            if rec.get("token") == x_persona_token:
                return {"ok": True, "persona": {"id": pid, **rec}}
        raise HTTPException(403, "invalid token")
    # otherwise return registry summary (admin-lite)
    return {"ok": True, "count": len(reg.get("personas", {})), "personas": reg.get("personas", {})}


class SyncIn:
    def __init__(self, blocks: List[Dict[str, Any]]):
        self.blocks = blocks


@router.post("/sync")
async def persona_sync(payload: Dict[str, Any], x_persona_token: Optional[str] = Header(None)):
    if not x_persona_token:
        raise HTTPException(401, "missing token")
    reg = _load_registry()
    # find persona by token
    pid = None
    for k, rec in reg.get("personas", {}).items():
        if rec.get("token") == x_persona_token:
            pid = k
            break
    if not pid:
        raise HTTPException(403, "invalid token")

    blocks = payload.get("blocks") or []
    if not isinstance(blocks, list):
        raise HTTPException(400, "blocks must be a list")

    bu = _load_block_utils()
    accepted: int = 0
    errors: List[str] = []
    for b in blocks:
        try:
            # only accept signed+valid blocks; function already checks.
            res = bu.validate_and_store_block(b)  # type: ignore
            if res.get("ok"):
                accepted += 1
            else:
                errors.append(res.get("reason") or "invalid")
        except Exception as e:
            errors.append(f"error:{type(e).__name__}")
            continue

    # update stats
    rec = reg["personas"][pid]
    rec["last_sync"] = _now_iso()
    rec["blocks"] = int(rec.get("blocks") or 0) + accepted
    _save_registry(reg)

    return {"ok": True, "accepted": accepted, "errors": errors}
