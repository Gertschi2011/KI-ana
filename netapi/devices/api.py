from __future__ import annotations

from typing import Dict, Any, List, Tuple
from .registry import list_devices as _list, get_device as _get
from .connectors import exec_device as _exec


def list_devices() -> List[Dict[str, Any]]:
    return _list()


def exec_device(dev_id: str, action: str, args: Dict[str, Any] | None = None) -> Tuple[bool, Dict[str, Any]]:
    dev = _get(dev_id)
    if not dev:
        return False, {"error": "device_not_found"}
    return _exec(dev, action, args or {})

