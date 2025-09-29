from apscheduler.schedulers.asyncio import AsyncIOScheduler
from ...brain import autonomous_tick, idle_tick
import os
from pathlib import Path

scheduler = AsyncIOScheduler()
AUTOPILOT = {"running": False, "job_id": "kiana_autopilot"}

async def tick():
    # Respect global emergency stop sentinel
    try:
        root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
        if (root / "emergency_stop").exists():
            return
    except Exception:
        pass
    try:
        # First, allow idle-driven self-learning (only triggers if bored)
        idle_tick()
    except Exception:
        pass
    # Then run a lightweight autonomous news-digest tick (net-allowed)
    try:
        await autonomous_tick()
    except Exception:
        pass
