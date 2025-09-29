from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Tuple, Optional, List
import os, shlex, subprocess, json, httpx

from .capabilities import ensure_cap

KI_ROOT = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))).resolve()
SAFE_FS_ROOTS = [KI_ROOT / "memory", KI_ROOT / "logs"]
for p in SAFE_FS_ROOTS: p.mkdir(parents=True, exist_ok=True)

def _normalize_under_roots(user_path: str) -> Path:
    p = (KI_ROOT / user_path.lstrip("/")).resolve()
    for root in SAFE_FS_ROOTS + [KI_ROOT]:
        if str(p).startswith(str(root.resolve())):
            return p
    # Fallback: verbieten
    raise PermissionError("path escapes allowed roots")

# ---------- Syscalls ----------

def sc_fs_read(role: str, path: str, max_bytes: int = 65536) -> Dict[str, Any]:
    ensure_cap(role, "fs.read")
    p = _normalize_under_roots(path)
    if not p.exists() or not p.is_file():
        return {"ok": False, "error": "not_found"}
    data = p.read_bytes()[:max_bytes]
    try:
        txt = data.decode("utf-8", errors="replace")
        return {"ok": True, "type": "text", "content": txt, "path": str(p)}
    except Exception:
        return {"ok": True, "type": "bytes", "content": list(data), "path": str(p)}

def sc_web_get(role: str, url: str, timeout: float = 10.0) -> Dict[str, Any]:
    ensure_cap(role, "web.get")
    # sehr simple Allowlist
    if not (url.startswith("http://") or url.startswith("https://")):
        return {"ok": False, "error": "invalid_url"}
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(url, headers={"User-Agent":"KI_ana/OS"})
        return {"ok": True, "status": r.status_code, "headers": dict(r.headers), "text": r.text[:200000]}

ALLOW_CMDS = {"uptime","whoami","date","ls"}

def sc_proc_run(role: str, cmd: str, timeout: float = 3.0) -> Dict[str, Any]:
    ensure_cap(role, "proc.run")
    parts = shlex.split(cmd)
    if not parts or parts[0] not in ALLOW_CMDS:
        return {"ok": False, "error": "command_not_allowed"}
    try:
        proc = subprocess.run(parts, capture_output=True, text=True, timeout=timeout)
        return {"ok": True, "rc": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}

# Memory-Bridge (nutzt deinen memory_adapter)
def sc_mem_store(role: str, title: str, content: str, tags: Optional[List[str]] = None, url: Optional[str] = None) -> Dict[str, Any]:
    ensure_cap(role, "mem.store")
    try:
        from ..chat.memory_adapter import store as mem_store
    except Exception:
        return {"ok": False, "error": "memory_unavailable"}
    p = mem_store(title=title, content=content, tags=tags or [], url=url, meta={"source":"os"})
    return {"ok": True, "path": str(p)}

def sc_mem_recall(role: str, query: str, top_k: int = 5) -> Dict[str, Any]:
    ensure_cap(role, "mem.recall")
    try:
        from ..chat.memory_adapter import recall as mem_recall
    except Exception:
        return {"ok": False, "error": "memory_unavailable"}
    hits = mem_recall(query, top_k=top_k)
    return {"ok": True, "results": hits}

def sc_notify_send(role: str, text: str) -> Dict[str, Any]:
    ensure_cap(role, "notify.send")
    logdir = KI_ROOT / "logs"; logdir.mkdir(parents=True, exist_ok=True)
    logf = logdir / "notifications.log"
    logf.write_text((logf.read_text(encoding="utf-8") if logf.exists() else "") + text + "\n", encoding="utf-8")
    return {"ok": True}