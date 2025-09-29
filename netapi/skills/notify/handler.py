from __future__ import annotations
from typing import Dict, Any
from ...modules.os.capabilities import ensure_cap
from ...modules.os import syscalls as sc

def run(action: str, args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    role = ctx.get("role","user")
    if action == "scheduled":
        return {"event":"tick"}
    if action == "ping":
        ensure_cap(role, "notify.send")
        txt = str(args.get("text","Ping von notify"))
        return sc.sc_notify_send(role, txt)
    if action == "digest":
        ensure_cap(role, "mem.store")
        title = "Daily Digest"
        content = args.get("content","(leer)")
        return sc.sc_mem_store(role, title=title, content=content, tags=["digest"])
    return {"ok": False, "error": "unknown_action"}
