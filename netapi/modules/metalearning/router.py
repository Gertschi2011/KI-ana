"""
Meta-Learning API Router
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Body
from pathlib import Path
from typing import Dict, Any, Optional
import sys

sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

router = APIRouter(prefix="/api/metalearning", tags=["metalearning"])


@router.post("/track")
async def track_metric(
    metric_name: str = Body(...),
    value: float = Body(...),
    context: Optional[Dict[str, Any]] = Body(None)
):
    """Track a performance metric."""
    try:
        from meta_learning import get_meta_learner
        learner = get_meta_learner()
        learner.track_metric(metric_name, value, context)
        return {"ok": True, "metric_name": metric_name, "value": value}
    except Exception as e:
        raise HTTPException(500, f"track_error: {e}")


@router.get("/analyze")
async def analyze_performance():
    """Analyze overall performance."""
    try:
        from meta_learning import get_meta_learner
        learner = get_meta_learner()
        analysis = learner.analyze_performance()
        return {"ok": True, "analysis": analysis}
    except Exception as e:
        raise HTTPException(500, f"analyze_error: {e}")


@router.get("/patterns")
async def identify_patterns():
    """Identify performance patterns."""
    try:
        from meta_learning import get_meta_learner
        learner = get_meta_learner()
        insights = learner.identify_patterns()
        return {
            "ok": True,
            "insights_count": len(insights),
            "insights": [i.to_dict() if hasattr(i, 'to_dict') else i for i in insights]
        }
    except Exception as e:
        raise HTTPException(500, f"patterns_error: {e}")


@router.get("/optimize")
async def optimize_strategies():
    """Generate optimization recommendations."""
    try:
        from meta_learning import get_meta_learner
        learner = get_meta_learner()
        result = learner.optimize_strategies()
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(500, f"optimize_error: {e}")


@router.get("/stats")
async def get_stats():
    """Get meta-learning statistics."""
    try:
        from meta_learning import get_meta_learner
        learner = get_meta_learner()
        stats = learner.get_stats()
        return {"ok": True, "stats": stats}
    except Exception as e:
        raise HTTPException(500, f"stats_error: {e}")
