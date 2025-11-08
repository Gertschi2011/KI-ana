"""
Dashboard Mock Router - Provides realistic mock data for dashboard features
that are not yet fully implemented in the backend.
"""
from fastapi import APIRouter, Query
from typing import List, Dict, Any
import time

router = APIRouter(prefix="/api", tags=["dashboard_mock"])

# ============================================================================
# PERSONALITY STATS MOCK
# ============================================================================

@router.get("/personality/stats")
async def get_personality_stats():
    """Mock endpoint for personality statistics"""
    return {
        "ok": True,
        "stats": {
            "interactions": 247,
            "positive_feedback": 189,
            "negative_feedback": 12,
            "feedback_rate": 0.813,
            "traits": {
                "Empathie": {
                    "current_value": 0.85,
                    "baseline": 0.75,
                    "trend": "increasing"
                },
                "Humor": {
                    "current_value": 0.62,
                    "baseline": 0.55,
                    "trend": "stable"
                },
                "Formalität": {
                    "current_value": 0.45,
                    "baseline": 0.50,
                    "trend": "decreasing"
                },
                "Kreativität": {
                    "current_value": 0.78,
                    "baseline": 0.70,
                    "trend": "increasing"
                }
            }
        }
    }

# ============================================================================
# AUTONOMOUS GOALS MOCK
# ============================================================================

@router.get("/goals/autonomous/stats")
async def get_goals_stats():
    """Mock endpoint for autonomous learning goals statistics"""
    return {
        "ok": True,
        "stats": {
            "total_goals": 12,
            "completed_goals": 4,
            "avg_priority": 0.67,
            "active_goals": 8,
            "gaps_identified": 23
        }
    }

@router.get("/goals/autonomous/top")
async def get_top_goals(n: int = Query(3, ge=1, le=10)):
    """Mock endpoint for top priority goals"""
    all_goals = [
        {
            "id": 1,
            "topic": "Machine Learning Grundlagen",
            "description": "Verbesserte Kenntnisse über Supervised Learning Algorithmen",
            "priority": 0.92,
            "keywords": ["ML", "Supervised Learning", "Algorithmen", "Training"],
            "created_at": int(time.time()) - 86400 * 7,
            "status": "active"
        },
        {
            "id": 2,
            "topic": "Konversationsführung",
            "description": "Natürlichere Gesprächsverläufe durch besseres Kontextverständnis",
            "priority": 0.85,
            "keywords": ["Dialog", "Kontext", "Natürlichkeit", "Flow"],
            "created_at": int(time.time()) - 86400 * 5,
            "status": "active"
        },
        {
            "id": 3,
            "topic": "Emotionale Intelligenz",
            "description": "Besseres Erkennen und Reagieren auf emotionale Zustände",
            "priority": 0.78,
            "keywords": ["Emotion", "Empathie", "Erkennung", "Response"],
            "created_at": int(time.time()) - 86400 * 3,
            "status": "active"
        },
        {
            "id": 4,
            "topic": "Code-Optimierung",
            "description": "Effizientere Algorithmen und bessere Performance",
            "priority": 0.71,
            "keywords": ["Performance", "Optimierung", "Effizienz", "Code"],
            "created_at": int(time.time()) - 86400 * 2,
            "status": "active"
        },
        {
            "id": 5,
            "topic": "Mehrsprachigkeit",
            "description": "Verbesserte Unterstützung für mehrsprachige Konversationen",
            "priority": 0.65,
            "keywords": ["Sprachen", "i18n", "Translation", "Multi-Lingual"],
            "created_at": int(time.time()) - 86400,
            "status": "active"
        }
    ]
    
    return {
        "ok": True,
        "goals": all_goals[:n]
    }

@router.get("/goals/autonomous/identify")
async def identify_gaps():
    """Mock endpoint for gap identification"""
    return {
        "ok": True,
        "gaps_found": 5,
        "message": "5 neue Wissenslücken identifiziert",
        "gaps": [
            "Quantencomputing Basics",
            "Blockchain Technologie",
            "Edge Computing",
            "IoT Protocols",
            "Neuromorphic Computing"
        ]
    }

# ============================================================================
# CONFLICT RESOLUTION MOCK
# ============================================================================

@router.get("/conflicts/stats")
async def get_conflicts_stats():
    """Mock endpoint for conflict resolution statistics"""
    return {
        "ok": True,
        "stats": {
            "total_resolutions": 18,
            "by_method": {
                "consensus": 8,
                "priority": 6,
                "merge": 4
            },
            "by_type": {
                "knowledge": 7,
                "behavior": 6,
                "preference": 5
            },
            "avg_resolution_time": 245.5,
            "success_rate": 0.94
        }
    }

# ============================================================================
# AUTO REFLECTION MOCK
# ============================================================================

@router.get("/reflection/auto/stats")
async def get_reflection_stats():
    """Mock endpoint for auto-reflection statistics"""
    return {
        "ok": True,
        "stats": {
            "enabled": True,
            "total_reflections": 34,
            "threshold": 50,
            "answer_count": 37,
            "next_reflection_in": 13,
            "last_reflection": int(time.time()) - 3600 * 12,
            "avg_insights": 3.2
        }
    }

@router.post("/reflection/auto/force")
async def force_reflection():
    """Mock endpoint for forcing a reflection"""
    return {
        "ok": True,
        "message": "Reflexion durchgeführt",
        "result": {
            "analyzed_answers": 37,
            "insights_found": 4,
            "improvements_suggested": 2,
            "timestamp": int(time.time())
        }
    }

# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "ok": True,
        "status": "running",
        "timestamp": int(time.time()),
        "modules": {
            "personality": "mock",
            "goals": "mock",
            "conflicts": "mock",
            "reflection": "mock"
        }
    }
