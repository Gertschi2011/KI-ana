"""
Self-Awareness Module
Provides KI_ana with knowledge about its own architecture
"""
from .router import router
from .system_map import get_system_map, get_system_summary

__all__ = ["router", "get_system_map", "get_system_summary"]
