from fastapi import APIRouter
from fastapi.responses import JSONResponse
import psutil, time

router = APIRouter(prefix="/api/system")

@router.get("/status")
def status():
    vm = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.2)
    procs = len(psutil.pids())
    return JSONResponse({
        "time": int(time.time()*1000),
        "cpu_percent": cpu,
        "ram_total": vm.total,
        "ram_used": vm.used,
        "ram_percent": vm.percent,
        "processes": procs
    })
