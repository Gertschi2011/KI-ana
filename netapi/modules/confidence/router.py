"""
Confidence Scoring API Router
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Body
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys

sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

router = APIRouter(prefix="/api/confidence", tags=["confidence"])


@router.post("/score/answer")
async def score_answer(
    text: str = Body(...),
    sources: Optional[List[Dict[str, Any]]] = Body(None),
    context: Optional[Dict[str, Any]] = Body(None)
):
    """Score confidence for an answer."""
    try:
        from confidence_scorer import get_confidence_scorer
        scorer = get_confidence_scorer()
        result = scorer.score_answer(text, sources, context)
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(500, f"scoring_error: {e}")


@router.post("/score/block")
async def score_block(block: Dict[str, Any] = Body(...)):
    """Score confidence for a knowledge block."""
    try:
        from confidence_scorer import get_confidence_scorer
        scorer = get_confidence_scorer()
        result = scorer.score_block(block)
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(500, f"scoring_error: {e}")
