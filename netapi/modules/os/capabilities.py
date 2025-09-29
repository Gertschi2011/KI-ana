from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

# Capability-Names (System-API)
CAPS = {
    "fs.read",
    "web.get",
    "proc.run",
    "mem.store",
    "mem.recall",
    "notify.send",
}

# Einfache Rollenmatrix
ROLE_CAPS: Dict[str, List[str]] = {
    "creator": list(CAPS),
    "admin":   ["fs.read","web.get","proc.run","mem.store","mem.recall","notify.send"],
    "user":    ["fs.read","web.get","mem.store","mem.recall","notify.send"],
    "guest":   ["fs.read","web.get"],
    # Sub‑KI (Kinder) – restriktive Rechte
    "child":   ["web.get","mem.store"],
}

def allowed_caps(role: str) -> List[str]:
    return ROLE_CAPS.get((role or "guest").lower(), ROLE_CAPS["guest"])

def ensure_cap(role: str, cap: str):
    if cap not in allowed_caps(role):
        raise PermissionError(f"capability denied: {cap}")
