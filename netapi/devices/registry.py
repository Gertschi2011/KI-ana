from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IDX_DIR = PROJECT_ROOT / "indexes" / "devices"
REGISTRY_PATH = IDX_DIR / "registry.json"


def _ensure() -> None:
    IDX_DIR.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_PATH.exists():
        REGISTRY_PATH.write_text(json.dumps({"devices": {}}, ensure_ascii=False, indent=2), encoding="utf-8")


def load_registry() -> Dict[str, Any]:
    _ensure()
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"devices": {}}


def save_registry(data: Dict[str, Any]) -> None:
    _ensure()
    REGISTRY_PATH.write_text(json.dumps(data or {"devices": {}}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def upsert_device(device: Dict[str, Any]) -> Dict[str, Any]:
    reg = load_registry()
    devs = reg.get("devices") or {}
    dev_id = str(device.get("id") or "").strip()
    if not dev_id:
        raise ValueError("device.id required")
    device["id"] = dev_id
    device.setdefault("enabled", True)
    device.setdefault("allowed_actions", [])
    devs[dev_id] = device
    reg["devices"] = devs
    save_registry(reg)
    return device


def get_device(dev_id: str) -> Optional[Dict[str, Any]]:
    reg = load_registry()
    return (reg.get("devices") or {}).get(str(dev_id))


def list_devices() -> List[Dict[str, Any]]:
    reg = load_registry()
    items = list((reg.get("devices") or {}).values())
    # hide secrets in config
    for it in items:
        cfg = it.get("config") or {}
        if isinstance(cfg, dict):
            for k in list(cfg.keys()):
                if k.lower() in {"token", "apikey", "api_key", "password", "secret"}:
                    cfg[k] = "***"
    return items

