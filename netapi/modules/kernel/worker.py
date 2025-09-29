# netapi/modules/kernel/worker.py
from __future__ import annotations
import json, sys, os, importlib, time
from typing import Dict, Any

# optionale Limits (Linux/Unix)
def _apply_limits(cpu_seconds=3, mem_mb=256, nfile=64):
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        resource.setrlimit(resource.RLIMIT_AS, (mem_mb*1024*1024, mem_mb*1024*1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (nfile, nfile))
    except Exception:
        pass

def _resolve(entrypoint: str):
    mod_path, fn_name = entrypoint.split(":", 1)
    mod = importlib.import_module(mod_path)
    fn  = getattr(mod, fn_name)
    if not callable(fn):
        raise TypeError("entrypoint not callable")
    return fn

def main():
    raw = sys.stdin.read()
    payload = json.loads(raw)
    entry = payload["entrypoint"]
    action = payload["action"]
    args = payload.get("args") or {}
    ctx  = payload.get("ctx") or {}
    limits = payload.get("limits") or {}
    _apply_limits(
        cpu_seconds=int(limits.get("cpu", 3)),
        mem_mb=int(limits.get("mem_mb", 256)),
        nfile=int(limits.get("nfile", 64)),
    )
    fn = _resolve(entry)
    if hasattr(fn, "__call__"):
        if hasattr(fn, "__code__") and fn.__code__.co_flags & 0x80:
            # async def
            import asyncio
            res = asyncio.run(fn(action=action, args=args, ctx=ctx))
        else:
            res = fn(action=action, args=args, ctx=ctx)
    else:
        res = {"ok": False, "error": "invalid_entrypoint"}
    if not isinstance(res, dict):
        res = {"ok": True, "result": res}
    sys.stdout.write(json.dumps({"ok": True, **res}, ensure_ascii=False))
    sys.stdout.flush()

if __name__ == "__main__":
    main()
