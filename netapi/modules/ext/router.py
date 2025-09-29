from __future__ import annotations
import asyncio
import os
import socket
import time
from pathlib import Path
from typing import Dict, Any, Optional
from subprocess import Popen

import httpx
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import Response

from ...deps import get_current_user_required, require_role

router = APIRouter(prefix="/api/ext", tags=["ext"])

# In-memory registry of running micro-tools
_PROCS: Dict[str, Dict[str, Any]] = {}


def _runtime_src(name: str) -> Path:
    root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))).resolve()
    return (root / "runtime" / "tools_src" / name).resolve()


def _find_free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return int(port)


def _is_running(p: Dict[str, Any]) -> bool:
    proc: Optional[Popen] = p.get("proc")
    if not proc:
        return False
    return (proc.poll() is None)


async def _healthcheck(port: int, path: str = "/", timeout_s: float = 2.0) -> bool:
    url = f"http://127.0.0.1:{int(port)}{path}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s)) as client:
            r = await client.get(url)
            return bool(r.status_code < 500)
    except Exception:
        return False


@router.get("/status")
async def status(user = Depends(get_current_user_required)):
    require_role(user, {"creator"})
    items = []
    for name, rec in list(_PROCS.items()):
        running = _is_running(rec)
        port = rec.get("port")
        healthy = False
        if running and port:
            healthy = await _healthcheck(int(port))
        items.append({
            "name": name,
            "port": port,
            "running": running,
            "healthy": healthy,
            "since": rec.get("started_at"),
            "cwd": rec.get("cwd"),
        })
    return {"ok": True, "items": items}


@router.post("/start")
async def start_tool(name: str, user = Depends(get_current_user_required)):
    require_role(user, {"creator"})
    n = (name or "").strip()
    if not n:
        raise HTTPException(400, "name required")
    base = _runtime_src(n)
    if not base.exists():
        raise HTTPException(404, "tool source not found")
    app_py = base / "app.py"
    if not app_py.exists():
        raise HTTPException(404, "app.py not found (only http micro-tools supported)")
    # If already running, return status
    rec = _PROCS.get(n)
    if rec and _is_running(rec):
        return {"ok": True, "name": n, "port": rec.get("port"), "running": True}
    # Spawn uvicorn with auto-retry ports and healthcheck
    attempts = 0
    last_err = None
    while attempts < 3:
        port = _find_free_port()
        cmd = [
            "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)
        ]
        try:
            log_path = base / 'uvicorn.out'
            err_path = base / 'uvicorn.err'
            log_f = open(log_path, 'ab')
            err_f = open(err_path, 'ab')
            proc = Popen(cmd, cwd=str(base), stdout=log_f, stderr=err_f)
        except FileNotFoundError as e:
            raise HTTPException(500, "uvicorn not found; please install uvicorn")
        _PROCS[n] = {"proc": proc, "port": port, "cwd": str(base), "started_at": int(time.time()), "log": str(log_path), "err": str(err_path)}
        # wait for readiness with small backoff
        ok = False
        for _ in range(10):
            await asyncio.sleep(0.2)
            if not _is_running(_PROCS[n]):
                last_err = "process exited prematurely"
                break
            if await _healthcheck(port):
                ok = True
                break
        if ok:
            return {"ok": True, "name": n, "port": port, "running": True}
        # otherwise try next port
        attempts += 1
        last_err = last_err or "healthcheck failed"
    raise HTTPException(502, f"failed to start tool after retries: {last_err}")


@router.post("/stop")
async def stop_tool(name: str, user = Depends(get_current_user_required)):
    require_role(user, {"creator"})
    n = (name or "").strip()
    rec = _PROCS.get(n)
    if not rec:
        return {"ok": True, "stopped": False}
    proc: Optional[Popen] = rec.get("proc")
    if proc and (proc.poll() is None):
        try:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except Exception:
                proc.kill()
        except Exception:
            pass
    _PROCS.pop(n, None)
    return {"ok": True, "stopped": True}


@router.api_route("/proxy/{name}/{path:path}", methods=["GET","POST","PUT","PATCH","DELETE"])
async def proxy(name: str, path: str, request: Request, user = Depends(get_current_user_required)):
    require_role(user, {"creator"})
    n = (name or "").strip()
    rec = _PROCS.get(n)
    if not rec or not _is_running(rec):
        raise HTTPException(404, "tool not running; start it via /api/ext/start?name=...")
    port = rec.get("port")
    if not port:
        raise HTTPException(500, "invalid port")
    target = f"http://127.0.0.1:{int(port)}/{path}".rstrip('/')
    # Build proxied request
    method = request.method
    headers = dict(request.headers)
    # Remove hop-by-hop headers
    headers.pop('host', None)
    headers.pop('connection', None)
    headers.pop('content-length', None)
    content = await request.body()
    timeout = httpx.Timeout(15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.request(method, target, headers=headers, content=content)
        except httpx.TimeoutException:
            raise HTTPException(504, "proxy timeout")
        except httpx.RequestError as e:
            raise HTTPException(502, f"proxy error: {e}")
    return Response(content=resp.content, status_code=resp.status_code, headers={k: v for k, v in resp.headers.items() if k.lower() in ("content-type","cache-control")})


@router.get('/logs')
async def logs(name: str, limit: int = 4000, user = Depends(get_current_user_required)):
    require_role(user, {"creator"})
    n = (name or '').strip()
    rec = _PROCS.get(n)
    if not rec:
        # try read files even if not running
        base = _runtime_src(n)
        if not base.exists():
            raise HTTPException(404, 'tool not found')
        log_p = base / 'uvicorn.out'
        err_p = base / 'uvicorn.err'
    else:
        log_p = Path(rec.get('log') or (_runtime_src(n)/'uvicorn.out'))
        err_p = Path(rec.get('err') or (_runtime_src(n)/'uvicorn.err'))
    out = b''
    err = b''
    try:
        if log_p.exists():
            with open(log_p, 'rb') as f:
                out = f.read()[-limit:]
        if err_p.exists():
            with open(err_p, 'rb') as f:
                err = f.read()[-limit:]
    except Exception:
        pass
    return {"ok": True, "stdout": out.decode('utf-8', 'ignore'), "stderr": err.decode('utf-8', 'ignore')}
