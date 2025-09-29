from fastapi import APIRouter, Depends, HTTPException, Request
from ...deps import get_db, require_user
from .service import scheduler, AUTOPILOT, tick
from ...config import settings

router = APIRouter()

@router.on_event("startup")
async def _start():
    try: scheduler.start()
    except Exception: pass
    # Optional auto-start job if env flag set
    try:
        import os
        from ...config import settings
        auto = os.getenv("AUTOPILOT_AUTO_START") or getattr(settings, "AUTOPILOT_AUTO_START", None)
        if str(auto).lower() in {"1","true","yes"}:
            from .service import AUTOPILOT
            from ...config import settings as _s
            if not AUTOPILOT["running"]:
                scheduler.add_job(tick, "interval", minutes=_s.AUTOPILOT_INTERVAL_MIN, id=AUTOPILOT["job_id"], replace_existing=True)
                AUTOPILOT["running"] = True
    except Exception:
        pass

@router.on_event("shutdown")
async def _stop():
    try: scheduler.shutdown(wait=False)
    except Exception: pass

@router.post("/start")
async def start(request: Request, db=Depends(get_db)):
    user = require_user(request, db)
    if user["role"] not in {"creator","admin"}: raise HTTPException(403, "Forbidden")
    if not AUTOPILOT["running"]:
        scheduler.add_job(tick, "interval", minutes=settings.AUTOPILOT_INTERVAL_MIN,
                          id=AUTOPILOT["job_id"], replace_existing=True)
        AUTOPILOT["running"] = True
    return {"ok": True, "running": True, "interval": f"{settings.AUTOPILOT_INTERVAL_MIN}m"}

@router.post("/stop")
async def stop(request: Request, db=Depends(get_db)):
    user = require_user(request, db)
    if user["role"] not in {"creator","admin"}: raise HTTPException(403, "Forbidden")
    if AUTOPILOT["running"]:
        try: scheduler.remove_job(AUTOPILOT["job_id"])
        except Exception: pass
        AUTOPILOT["running"] = False
    return {"ok": True, "running": False}
