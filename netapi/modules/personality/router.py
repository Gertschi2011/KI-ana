"""
Personality API Router

Provides endpoints for managing dynamic personality.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import Dict, Any
import sys

# Add system path for imports
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

router = APIRouter(prefix="/api/personality", tags=["personality"])


@router.get("/stats")
async def get_personality_stats():
    """Get current personality statistics."""
    try:
        from dynamic_personality import get_dynamic_personality
        personality = get_dynamic_personality()
        stats = personality.get_stats()
        return {"ok": True, "stats": stats}
    except Exception as e:
        raise HTTPException(500, f"failed to get stats: {e}")


@router.get("/traits")
async def get_current_traits():
    """Get current trait values (with context applied)."""
    try:
        from dynamic_personality import get_dynamic_personality
        personality = get_dynamic_personality()
        traits = personality.get_current_traits()
        return {"ok": True, "traits": traits}
    except Exception as e:
        raise HTTPException(500, f"failed to get traits: {e}")


@router.post("/traits/{trait_name}/reset")
async def reset_trait(trait_name: str):
    """Reset a specific trait to its base value."""
    try:
        from dynamic_personality import get_dynamic_personality
        personality = get_dynamic_personality()
        success = personality.reset_trait(trait_name)
        if not success:
            raise HTTPException(404, f"trait '{trait_name}' not found")
        return {"ok": True, "trait": trait_name, "reset": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"failed to reset trait: {e}")


@router.post("/traits/reset_all")
async def reset_all_traits():
    """Reset all traits to base values."""
    try:
        from dynamic_personality import get_dynamic_personality
        personality = get_dynamic_personality()
        personality.reset_all_traits()
        return {"ok": True, "reset": "all"}
    except Exception as e:
        raise HTTPException(500, f"failed to reset all traits: {e}")


@router.post("/detect_mood")
async def detect_user_mood(text: str):
    """Detect user mood from text."""
    try:
        from dynamic_personality import get_dynamic_personality
        personality = get_dynamic_personality()
        mood = personality.detect_user_mood(text)
        return {"ok": True, "mood": mood, "text": text[:100]}
    except Exception as e:
        raise HTTPException(500, f"failed to detect mood: {e}")
