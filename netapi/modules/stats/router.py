from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import Dict, Any
import os, time, shutil
from urllib.request import urlopen
try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # type: ignore

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics")
def metrics():
    root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
    mem_blocks = list((root / "memory" / "long_term" / "blocks").glob("*.json"))
    chain_blocks = list((root / "system" / "chain").glob("*.json"))
    emergency_active = (root / "emergency_stop").exists()

    # Jobs count
    try:
        from ..kernel.scheduler import SCHED  # type: ignore
        jobs = len(SCHED.list())
    except Exception:
        jobs = 0

    # LLM availability (no dependency on requests or llm_local import)
    # Read host/model from settings first, then env, else sensible defaults
    host = None
    model = None
    try:
        from ..config import settings  # type: ignore
        host = getattr(settings, "OLLAMA_HOST", None)
        model = getattr(settings, "OLLAMA_MODEL", None)
    except Exception:
        pass
    host = (host or os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")
    model = (model or os.getenv("OLLAMA_MODEL", None))
    # Ping /api/tags with short timeout
    try:
        with urlopen(f"{host}/api/tags", timeout=2) as r:
            ollama = (getattr(r, "status", 200) == 200)
    except Exception:
        ollama = False

    # Network access flag
    try:
        from ..config import settings  # type: ignore
        net_ok = bool(getattr(settings, "ALLOW_NET", True))
    except Exception:
        net_ok = os.getenv("ALLOW_NET", "1") == "1"

    return JSONResponse({
        "ts": int(time.time()),
        "memory_blocks": len(mem_blocks),
        "chain_blocks": len(chain_blocks),
        "jobs": jobs,
        "emergency_active": emergency_active,
        "net_access": net_ok,
        "ollama": {"available": ollama, "model": model, "host": host},
    })


@router.get("/resources")
def resources() -> Dict[str, Any]:
    """Lightweight system resource snapshot for Papa menu UI."""
    now = int(time.time())
    data: Dict[str, Any] = {"ts": now}
    root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
    # CPU
    try:
        if psutil is not None:
            data["cpu_percent"] = psutil.cpu_percent(interval=0.0)
            data["cpu_count"] = psutil.cpu_count(logical=True)
        else:
            data["cpu_percent"] = None
            data["cpu_count"] = os.cpu_count()
    except Exception:
        data["cpu_percent"] = None
        data["cpu_count"] = os.cpu_count()
    # Load average
    try:
        la1, la5, la15 = os.getloadavg()
        data["loadavg"] = {"1m": la1, "5m": la5, "15m": la15}
    except Exception:
        data["loadavg"] = None
    # Memory
    try:
        if psutil is not None:
            vm = psutil.virtual_memory()
            data["memory"] = {"total": vm.total, "used": vm.used, "percent": vm.percent}
        else:
            meminfo = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    k, v = line.split(":", 1)
                    meminfo[k.strip()] = v.strip()
            def _kbt(x):
                try:
                    return int(x.split()[0]) * 1024
                except Exception:
                    return None
            total = _kbt(meminfo.get("MemTotal", "0 kB"))
            free = _kbt(meminfo.get("MemAvailable", meminfo.get("MemFree", "0 kB")))
            used = (total - free) if (total is not None and free is not None) else None
            pct = (used * 100.0 / total) if (used is not None and total) else None
            data["memory"] = {"total": total, "used": used, "percent": pct}
    except Exception:
        data["memory"] = None
    # Disk (KI_ROOT)
    try:
        du = shutil.disk_usage(str(root))
        data["disk"] = {"total": du.total, "used": du.used, "free": du.free, "percent": (du.used * 100.0 / du.total if du.total else None)}
    except Exception:
        data["disk"] = None
    # Network I/O
    try:
        if psutil is not None:
            nio = psutil.net_io_counters()
            data["net_io"] = {"bytes_sent": nio.bytes_sent, "bytes_recv": nio.bytes_recv, "packets_sent": nio.packets_sent, "packets_recv": nio.packets_recv}
        else:
            data["net_io"] = None
    except Exception:
        data["net_io"] = None
    # Uptime
    try:
        if psutil is not None and hasattr(psutil, 'boot_time'):
            data["uptime_seconds"] = int(time.time() - psutil.boot_time())
        else:
            with open('/proc/uptime','r') as f:
                up = float(f.read().split()[0])
            data["uptime_seconds"] = int(up)
    except Exception:
        data["uptime_seconds"] = None
    # Current process
    try:
        if psutil is not None:
            p = psutil.Process()
            mem = p.memory_info()
            data["process"] = {
                "pid": p.pid,
                "rss": mem.rss,
                "vms": mem.vms,
                "cpu_percent": p.cpu_percent(interval=0.0),
                "num_threads": p.num_threads(),
            }
        else:
            data["process"] = {"pid": os.getpid()}
    except Exception:
        data["process"] = None
    # Processes
    try:
        if psutil is not None:
            data["procs"] = {
                "count": len(psutil.pids()),
                "self_open_files": len(psutil.Process().open_files()),
            }
        else:
            # Fallback count via /proc
            data["procs"] = {"count": len([d for d in os.listdir("/proc") if d.isdigit()])}
    except Exception:
        data["procs"] = None
    return data


@router.get("/system/status")
def system_status() -> Dict[str, Any]:
    """Unified system status snapshot.

    Combines quick metrics (jobs, chain/memory counts, ollama availability)
    with resource stats (cpu, mem, disk, net, uptime, process).
    """
    # Reuse existing helpers to avoid duplication
    try:
        metrics = metrics()  # type: ignore
    except Exception:
        metrics = {"ts": int(time.time())}
    try:
        res = resources()
    except Exception:
        res = {}
    out: Dict[str, Any] = {
        "ok": True,
        "ts": int(time.time()),
        "metrics": metrics,
        "resources": res,
    }
    # Add basic process/env info
    try:
        out["env"] = {
            "hostname": os.uname().nodename if hasattr(os, "uname") else None,
            "root": str(Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))),
        }
    except Exception:
        pass
    return out
