"""
Emotion API Router
Provides access to emotional state and detection
Sprint 7.2 - Emotionale Resonanz
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from .affect_engine import get_affect_engine


router = APIRouter(prefix="/api/emotion", tags=["emotion"])


class EmotionDetectionRequest(BaseModel):
    """Request for emotion detection"""
    text: str
    audio_features: Optional[Dict[str, float]] = None


@router.get("/state")
async def get_emotion_state():
    """
    Get current emotional state
    
    Returns KI_ana's current emotional state including:
    - current_emotion
    - intensity
    - last_user_emotion
    - resonance_level
    """
    engine = get_affect_engine()
    state = engine.get_state()
    
    return JSONResponse({
        "ok": True,
        "state": state
    })


@router.post("/detect")
async def detect_emotion(request: EmotionDetectionRequest):
    """
    Detect emotion from text (and optional audio features)
    
    Analyzes user input and returns detected emotion with intensity.
    """
    engine = get_affect_engine()
    
    emotion, intensity = engine.detect_emotion(
        request.text,
        request.audio_features
    )
    
    # Get resonance parameters
    params = engine.get_resonance_parameters(emotion, intensity)
    
    return JSONResponse({
        "ok": True,
        "emotion": emotion,
        "intensity": intensity,
        "resonance_parameters": params
    })


@router.get("/history")
async def get_emotion_history():
    """
    Get emotion history
    
    Returns last 10 detected emotions.
    """
    engine = get_affect_engine()
    state = engine.get_state()
    
    history = state.get('emotion_history', [])
    
    return JSONResponse({
        "ok": True,
        "history": history,
        "count": len(history)
    })
