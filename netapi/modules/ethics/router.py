from __future__ import annotations
from fastapi import APIRouter
from typing import Dict, Any

from ki_ana.system.ethical_guard import check_block

router = APIRouter(prefix="/evaluate_ethics", tags=["ethics"])

@router.post("")
async def evaluate(block: Dict[str, Any]):
    """Evaluate a knowledge block for ethics/safety.
    Expected block keys: title, content (others are ignored).
    """
    try:
        res = check_block(block or {})
        return {"ok": True, "assessment": res}
    except Exception as e:
        return {"ok": False, "error": str(e)}
