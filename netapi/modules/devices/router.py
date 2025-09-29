from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from ...deps import get_current_user_required, require_role
from ...devices.registry import upsert_device, list_devices, get_device
from ...devices.connectors import exec_device as _exec


router = APIRouter(prefix="/api/devices", tags=["devices"]) 


class DeviceIn(BaseModel):
    id: str = Field(..., min_length=1, max_length=120)
    name: str
    protocol: str = Field(..., description="http|webhook|mqtt")
    kind: Optional[str] = None
    enabled: Optional[bool] = True
    allowed_actions: Optional[List[str]] = []
    config: Dict[str, Any] = {}


class ExecIn(BaseModel):
    action: str
    args: Optional[Dict[str, Any]] = {}


def _require_admin_or_worker(user: Dict[str, Any]):
    # Admin or Worker ("creator" remains compatible via alias in deps)
    require_role(user, {"admin", "worker"})


def _audit_device(event: Dict[str, Any]) -> None:
    try:
        from pathlib import Path
        import json, time, os
        root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
        logdir = root / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        event = dict(event)
        event.setdefault("ts", int(time.time()))
        (logdir / "audit_devices.jsonl").open("a", encoding="utf-8").write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


@router.get("")
async def api_list(user = Depends(get_current_user_required)):
    return {"items": list_devices()}


@router.get("/{dev_id}")
async def api_get(dev_id: str, user = Depends(get_current_user_required)):
    dev = get_device(dev_id)
    if not dev:
        raise HTTPException(404, "device_not_found")
    # hide secrets
    cfg = dev.get("config") or {}
    if isinstance(cfg, dict):
        for k in list(cfg.keys()):
            if k.lower() in {"token", "apikey", "api_key", "password", "secret"}:
                cfg[k] = "***"
    return dev


@router.post("")
async def api_register(body: DeviceIn, user = Depends(get_current_user_required)):
    _require_admin_or_worker(user)
    dev = upsert_device(body.dict())
    try: _audit_device({"evt":"register","by":user.get("username"),"dev":dev.get("id")})
    except Exception: pass
    # hide secrets in echo
    cfg = dev.get("config") or {}
    if isinstance(cfg, dict):
        for k in list(cfg.keys()):
            if k.lower() in {"token", "apikey", "api_key", "password", "secret"}:
                cfg[k] = "***"
    return {"ok": True, "device": dev}


@router.post("/{dev_id}/exec")
async def api_exec(dev_id: str, body: ExecIn, user = Depends(get_current_user_required)):
    _require_admin_or_worker(user)
    ok, res = _exec(get_device(dev_id) or {}, body.action, body.args or {})
    try:
        _audit_device({
            "evt":"exec","by":user.get("username"),"dev":dev_id,
            "action": body.action, "args": body.args or {}, "ok": ok,
        })
    except Exception:
        pass
    if not ok:
        raise HTTPException(400, res.get("error", "exec_failed"))
    return {"ok": True, "result": res}
