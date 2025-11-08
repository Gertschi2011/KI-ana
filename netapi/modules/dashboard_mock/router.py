"""
Dashboard Mock Router - Provides realistic mock data for dashboard features
that are not yet fully implemented in the backend.
"""
from fastapi import APIRouter, Query
from typing import List, Dict, Any
import time, random

router = APIRouter(prefix="/api", tags=["dashboard_mock"])

# In-memory mutable state so the dashboard can show changes over time
_STATE = {
    "goals": {
        "total_goals": 12,
        "completed_goals": 4,
        "avg_priority": 0.67,
        "active_goals": 8,
        "gaps_identified": 23,
        "top": [
            {"id": 1, "topic": "Machine Learning Grundlagen", "description": "Verbesserte Kenntnisse über Supervised Learning Algorithmen", "priority": 0.92, "keywords": ["ML", "Supervised Learning", "Algorithmen", "Training"], "created_at": int(time.time()) - 86400 * 7, "status": "active"},
            {"id": 2, "topic": "Konversationsführung", "description": "Natürlichere Gesprächsverläufe durch besseres Kontextverständnis", "priority": 0.85, "keywords": ["Dialog", "Kontext", "Natürlichkeit", "Flow"], "created_at": int(time.time()) - 86400 * 5, "status": "active"},
            {"id": 3, "topic": "Emotionale Intelligenz", "description": "Besseres Erkennen und Reagieren auf emotionale Zustände", "priority": 0.78, "keywords": ["Emotion", "Empathie", "Erkennung", "Response"], "created_at": int(time.time()) - 86400 * 3, "status": "active"},
            {"id": 4, "topic": "Code-Optimierung", "description": "Effizientere Algorithmen und bessere Performance", "priority": 0.71, "keywords": ["Performance", "Optimierung", "Effizienz", "Code"], "created_at": int(time.time()) - 86400 * 2, "status": "active"},
            {"id": 5, "topic": "Mehrsprachigkeit", "description": "Verbesserte Unterstützung für mehrsprachige Konversationen", "priority": 0.65, "keywords": ["Sprachen", "i18n", "Translation", "Multi-Lingual"], "created_at": int(time.time()) - 86400, "status": "active"},
        ],
    },
    "reflection": {
        "enabled": True,
        "total_reflections": 34,
        "threshold": 50,
        "answer_count": 37,
        "next_reflection_in": 13,
        "last_reflection": int(time.time()) - 3600 * 12,
        "avg_insights": 3.2,
    },
    "conflicts": {
        "total_resolutions": 18,
        "by_method": {"consensus": 8, "priority": 6, "merge": 4},
        "by_type": {"knowledge": 7, "behavior": 6, "preference": 5},
        "avg_resolution_time": 245.5,
        "success_rate": 0.94,
    }
}

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
    g = _STATE["goals"]
    return {"ok": True, "stats": {
        "total_goals": g["total_goals"],
        "completed_goals": g["completed_goals"],
        "avg_priority": g["avg_priority"],
        "active_goals": g["active_goals"],
        "gaps_identified": g["gaps_identified"],
    }}

@router.get("/goals/autonomous/top")
async def get_top_goals(n: int = Query(3, ge=1, le=10)):
    """Mock endpoint for top priority goals"""
    return {"ok": True, "goals": _STATE["goals"]["top"][:n]}

@router.get("/goals/autonomous/identify")
async def identify_gaps():
    """Mock endpoint for gap identification"""
    # Simuliere Änderungen an Zielen
    add = random.randint(1, 3)
    g = _STATE["goals"]
    g["total_goals"] += add
    g["active_goals"] += add
    g["gaps_identified"] += add
    g["avg_priority"] = max(0.3, min(0.95, g["avg_priority"] + random.uniform(-0.03, 0.04)))
    # Optionale neue Top-Goal hinzufügen
    new_id = max(goal["id"] for goal in g["top"]) + 1
    g["top"].insert(0, {
        "id": new_id,
        "topic": f"Neues Lernziel #{new_id}",
        "description": "Automatisch identifiziertes Wissensziel",
        "priority": round(random.uniform(0.6, 0.95), 2),
        "keywords": ["Auto", "Gap", "Learning"],
        "created_at": int(time.time()),
        "status": "active",
    })
    return {"ok": True, "gaps_found": add, "message": f"{add} neue Wissenslücken identifiziert", "gaps": [g["top"][0]["topic"]]}

# ============================================================================
# CONFLICT RESOLUTION MOCK
# ============================================================================

@router.get("/conflicts/stats")
async def get_conflicts_stats():
    """Mock endpoint for conflict resolution statistics"""
    return {"ok": True, "stats": _STATE["conflicts"]}

# ============================================================================
# AUTO REFLECTION MOCK
# ============================================================================

@router.get("/reflection/auto/stats")
async def get_reflection_stats():
    """Mock endpoint for auto-reflection statistics"""
    return {"ok": True, "stats": _STATE["reflection"]}

@router.post("/reflection/auto/force")
async def force_reflection():
    """Mock endpoint for forcing a reflection"""
    r = _STATE["reflection"]
    # Simuliere eine durchgeführte Reflexion
    r["total_reflections"] += 1
    r["last_reflection"] = int(time.time())
    # Reset Zyklus: Antwortzähler zurücksetzen, neue Rest-Schritte bis zur nächsten Reflexion
    r["answer_count"] = 0
    r["next_reflection_in"] = r["threshold"]
    r["avg_insights"] = round(max(1.5, min(5.0, r["avg_insights"] + random.uniform(-0.2, 0.3))), 2)
    return {"ok": True, "message": "Reflexion durchgeführt", "result": {
        "analyzed_answers": r["threshold"],
        "insights_found": int(1 + r["avg_insights"] // 1),
        "improvements_suggested": random.randint(1, 3),
        "timestamp": r["last_reflection"],
    }}

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
