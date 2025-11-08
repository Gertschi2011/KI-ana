"""TimeFlow API Router - Endpoints for internal time perception system."""

from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from netapi.deps import get_current_user_required, require_role
import json, asyncio

# SSE optional import
try:
    from sse_starlette.sse import EventSourceResponse  # type: ignore
except Exception:
    EventSourceResponse = None  # type: ignore

# Import from parent app.py (will be refactored)
# For now, endpoints will be added to app.py that import this router

router = APIRouter(prefix="/api/timeflow", tags=["timeflow"])


class TimeFlowConfigUpdate(BaseModel):
    """Configuration update model for TimeFlow."""
    interval_sec: Optional[float] = None
    log_window: Optional[int] = None
    activation_decay: Optional[float] = None
    stimulus_weight: Optional[float] = None
    path_weights: Optional[Dict[str, float]] = None
    circadian_enabled: Optional[bool] = None
    circadian_amplitude: Optional[float] = None
    circadian_phase_shift_h: Optional[float] = None
    circadian_min_floor: Optional[float] = None
    alert_activation_warn: Optional[float] = None
    alert_activation_crit: Optional[float] = None
    alert_reqs_per_min_warn: Optional[float] = None
    alert_reqs_per_min_crit: Optional[float] = None
    alert_emotion_warn: Optional[float] = None
    alert_emotion_crit: Optional[float] = None


class AlertMuteRequest(BaseModel):
    """Request to mute an alert kind."""
    kind: str
    duration_sec: float = 300.0  # 5 minutes default


def get_timeflow():
    """Get the global TimeFlow instance from app.py."""
    # This will be imported from app.py
    from netapi.app import TIMEFLOW
    return TIMEFLOW


@router.get("/")
def timeflow_state(user = Depends(get_current_user_required)):
    """
    Get current TimeFlow state snapshot.
    
    Returns the current internal clock state including:
    - tick count and timestamp
    - event/request density
    - activation level
    - subjective time accumulator
    - emotion level
    - circadian factor
    """
    try:
        tf = get_timeflow()
        snap = tf.snapshot()
        return {"ok": True, "timeflow": snap}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/history")
def timeflow_history(
    limit: int = Query(200, ge=1, le=1000),
    user = Depends(get_current_user_required)
):
    """
    Get TimeFlow history (recent ticks).
    
    Args:
        limit: Number of historical snapshots to return (1-1000)
    
    Returns:
        List of historical TimeFlow state snapshots.
    """
    try:
        tf = get_timeflow()
        history = tf.history(limit)
        return {"ok": True, "history": history, "count": len(history)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/config")
def timeflow_config(user = Depends(get_current_user_required)):
    """
    Get current TimeFlow configuration.
    
    Requires: admin or owner role.
    """
    try:
        require_role(user, {"admin", "owner"})
    except Exception:
        return JSONResponse(status_code=403, content={"ok": False, "error": "forbidden"})
    
    try:
        tf = get_timeflow()
        config = tf.get_config()
        return {"ok": True, "config": config}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("/config")
def update_timeflow_config(
    body: TimeFlowConfigUpdate,
    user = Depends(get_current_user_required)
):
    """
    Update TimeFlow configuration (runtime tuning).
    
    Requires: admin or owner role.
    
    Allows runtime adjustment of:
    - Activation decay rate
    - Stimulus sensitivity
    - Circadian rhythm parameters
    - Alert thresholds
    - Path-specific request weights
    """
    try:
        require_role(user, {"admin", "owner"})
    except Exception:
        return JSONResponse(status_code=403, content={"ok": False, "error": "forbidden"})
    
    try:
        tf = get_timeflow()
        # Convert to dict, filter None values
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        applied = tf.apply_config(updates)
        return {"ok": True, "applied": applied, "message": f"Applied {len(applied)} config changes"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/alerts")
def timeflow_alerts(
    limit: int = Query(50, ge=1, le=200),
    user = Depends(get_current_user_required)
):
    """
    Get recent TimeFlow alerts.
    
    Args:
        limit: Number of recent alerts to return (1-200)
    
    Returns:
        Recent alerts (activation warnings, anomaly detections, etc.)
    """
    try:
        tf = get_timeflow()
        alerts = tf.alerts(limit)
        total = tf.alerts_total()
        counters = tf.alert_counters()
        return {
            "ok": True,
            "alerts": alerts,
            "count": len(alerts),
            "total": total,
            "counters": counters
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("/alerts/mute")
def mute_timeflow_alert(
    body: AlertMuteRequest,
    user = Depends(get_current_user_required)
):
    """
    Mute a specific alert kind temporarily.
    
    Requires: admin or owner role.
    
    Args:
        kind: Alert kind to mute (e.g. "activation_warn", "anomaly_crit")
        duration_sec: Duration in seconds to mute (default: 300 = 5 minutes)
    """
    try:
        require_role(user, {"admin", "owner"})
    except Exception:
        return JSONResponse(status_code=403, content={"ok": False, "error": "forbidden"})
    
    try:
        tf = get_timeflow()
        tf.mute_alert(body.kind, body.duration_sec)
        import time
        mute_until = time.time() + body.duration_sec
        return {
            "ok": True,
            "message": f"Muted '{body.kind}' for {body.duration_sec}s",
            "mute_until": int(mute_until * 1000)
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/stats")
def timeflow_stats(user = Depends(get_current_user_required)):
    """
    Get TimeFlow statistics and metadata.
    
    Returns:
        - Webhook queue stats
        - Compaction status
        - Pruned files count
    """
    try:
        tf = get_timeflow()
        stats = {
            "webhook_dropped_total": tf.webhook_dropped_total(),
            "pruned_files_total": tf.pruned_files_total(),
            "last_compact_ts": tf.last_compact_ts(),
        }
        return {"ok": True, "stats": stats}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/stream")
async def timeflow_stream(user = Depends(get_current_user_required)):
    """
    Stream TimeFlow updates via SSE.
    
    Sends TimeFlow state snapshots every 2 seconds.
    """
    if EventSourceResponse is None:
        return JSONResponse(status_code=501, content={"ok": False, "error": "SSE not available"})
    
    async def generate():
        try:
            tf = get_timeflow()
            while True:
                try:
                    snap = tf.snapshot()
                    yield {"data": json.dumps(snap)}
                    await asyncio.sleep(2)
                except Exception:
                    await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass
    
    return EventSourceResponse(generate(), ping=15)


# ==================== PHASE 9: LIFECYCLE API ====================

from .lifecycle import get_lifecycle_engine


@router.get("/lifecycle/age")
def get_lifecycle_age(user = Depends(get_current_user_required)):
    """
    Get KI_ana's age in various formats
    
    Returns:
    - Chronological age (real time)
    - Cycle age (total cycles, weighted)
    - Subjective age (based on experience)
    - Current life phase
    """
    try:
        engine = get_lifecycle_engine()
        age = engine.get_age()
        return {"ok": True, "age": age}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/lifecycle/summary")
def get_lifecycle_summary(user = Depends(get_current_user_required)):
    """
    Get complete lifecycle summary
    
    Returns full lifecycle state including:
    - Age information
    - Diary entries count
    - Compressed memories
    - Vitality metrics
    """
    try:
        engine = get_lifecycle_engine()
        summary = engine.get_lifecycle_summary()
        return {"ok": True, "summary": summary}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("/lifecycle/cycle")
def record_lifecycle_cycle(
    cycle_type: str = Query(..., description="Type of cycle (audit, mirror, dialog, etc.)"),
    duration_ms: int = Query(0, description="Duration in milliseconds"),
    user = Depends(get_current_user_required)
):
    """
    Record a lifecycle cycle
    
    Args:
        cycle_type: Type of cycle (audit, mirror, dialog, reflection, creation)
        duration_ms: Duration in milliseconds
    
    This is typically called automatically by other systems,
    but can be manually triggered for testing.
    """
    try:
        require_role(user, {"admin", "papa", "creator"})
        
        engine = get_lifecycle_engine()
        entry = engine.record_cycle(cycle_type, duration_ms)
        
        return {
            "ok": True,
            "entry": entry,
            "message": f"Recorded {cycle_type} cycle"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
