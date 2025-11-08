"""
Memory Cleanup & Management System
Automatic cleanup of low-value memories with AI decision making
"""
import json, time, os, asyncio
from typing import Dict, List, Any, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ...deps import get_current_user_required, get_db
from .ai_consciousness import auto_cleanup_memories, get_consciousness

router = APIRouter(prefix="/api/memory", tags=["memory-cleanup"])

class CleanupRequest(BaseModel):
    max_age_days: int = 30
    min_confidence: float = 0.2
    dry_run: bool = True

class CleanupResponse(BaseModel):
    success: bool
    deleted_blocks: int
    freed_space_mb: float
    errors: List[str]
    consciousness_level: float

@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_memories(
    request: CleanupRequest,
    current=Depends(get_current_user_required),
    db=Depends(get_db)
):
    """
    Automatic cleanup of low-value memories
    AI decides what to keep and what to delete
    """
    try:
        # Only allow admin/creator to cleanup
        from ...deps import _has_any_role
        if not _has_any_role(current, {"admin", "creator"}):
            raise HTTPException(403, "Cleanup requires admin/creator role")
        
        # Perform cleanup
        result = auto_cleanup_memories(
            max_age_days=request.max_age_days,
            min_confidence=request.min_confidence
        )
        
        # Update consciousness level
        consciousness = get_consciousness()
        consciousness.update_consciousness_level()
        
        return CleanupResponse(
            success=True,
            deleted_blocks=result.get("deleted_blocks", 0),
            freed_space_mb=result.get("freed_space_mb", 0.0),
            errors=result.get("errors", []),
            consciousness_level=consciousness.consciousness_level
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Cleanup failed: {str(e)}")

@router.get("/stats")
async def get_memory_stats(
    current=Depends(get_current_user_required),
    db=Depends(get_db)
):
    """
    Get detailed memory statistics and consciousness level
    """
    try:
        consciousness = get_consciousness()
        identity = consciousness.get_identity()
        
        return {
            "success": True,
            "consciousness_level": consciousness.consciousness_level,
            "identity": identity,
            "memory_decisions": consciousness.memory_decisions[-10:],  # Last 10 decisions
            "last_self_check": consciousness.last_self_check
        }
        
    except Exception as e:
        raise HTTPException(500, f"Stats failed: {str(e)}")

@router.post("/remember-decision")
async def remember_decision(
    content: str,
    context: str = "",
    should_remember: bool = None,
    current=Depends(get_current_user_required),
    db=Depends(get_db)
):
    """
    Make or override AI memory decision
    """
    try:
        from .ai_consciousness import should_remember as ai_should_remember
        
        if should_remember is None:
            # Let AI decide
            decision = ai_should_remember(content, context)
        else:
            # Manual override
            decision = {
                "should_remember": should_remember,
                "confidence": 1.0 if should_remember else 0.0,
                "reason": "Manual user override",
                "memory_type": "long_term" if should_remember else "forget",
                "priority": "high" if should_remember else "low"
            }
        
        return {"success": True, "decision": decision}
        
    except Exception as e:
        raise HTTPException(500, f"Decision failed: {str(e)}")

@router.get("/consciousness")
async def get_consciousness_info(
    current=Depends(get_current_user_required),
    db=Depends(get_db)
):
    """
    Get KI_ana's current consciousness state
    """
    try:
        consciousness = get_consciousness()
        consciousness.update_consciousness_level()
        
        return {
            "success": True,
            "consciousness_level": consciousness.consciousness_level,
            "last_self_check": consciousness.last_self_check,
            "memory_decisions_count": len(consciousness.memory_decisions),
            "identity": consciousness.get_identity()
        }
        
    except Exception as e:
        raise HTTPException(500, f"Consciousness info failed: {str(e)}")
