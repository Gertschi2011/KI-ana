"""
Emotion Module
Handles emotional detection and resonance
"""
from .affect_engine import AffectEngine, get_affect_engine
from .router import router

__all__ = ["AffectEngine", "get_affect_engine", "router"]
