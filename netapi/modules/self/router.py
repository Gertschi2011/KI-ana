from __future__ import annotations
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pathlib import Path
from importlib.machinery import SourceFileLoader
import json
import os

router = APIRouter(prefix="/self", tags=["self"]) 
BASE_DIR = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"


def _load_self_reflection():
    mod = SourceFileLoader("self_reflection", str(BASE_DIR / "system" / "self_reflection.py")).load_module()  # type: ignore
    return mod


def _recent_learnings(limit: int = 5):
    items = []
    for p in sorted(BLOCKS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:100]:
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        tags = [t.lower() for t in (b.get("tags") or [])]
        if any(t in tags for t in ("update", "reflection", "feedback")):
            items.append({
                "id": b.get("id"),
                "title": b.get("title"),
                "topic": b.get("topic"),
                "timestamp": b.get("timestamp"),
                "tags": b.get("tags"),
            })
        if len(items) >= limit:
            break
    return items


@router.get("")
async def get_self():
    sr = _load_self_reflection()
    ident = sr.get_identity()  # type: ignore
    recent = _recent_learnings()
    return JSONResponse({"ok": True, "identity": ident, "recent": recent})


# ========== SYSTEM MAP (SPRINT 6.1) ==========

from .system_map import get_system_map, get_system_summary, explain_capability


@router.get("/system/map")
async def get_system_map_endpoint(
    include_dynamic: bool = Query(True, description="Include dynamic statistics"),
    format: str = Query("full", description="full or summary")
):
    """
    Get system architecture map
    
    Returns complete self-knowledge about KI_ana's capabilities,
    architecture, and current state.
    """
    if format == "summary":
        data = get_system_summary()
    else:
        data = get_system_map(include_dynamic=include_dynamic)
    
    return JSONResponse({"ok": True, "data": data})


@router.get("/system/capability/{capability}")
async def explain_capability_endpoint(capability: str):
    """
    Get explanation for a specific capability
    """
    explanation = explain_capability(capability)
    
    if not explanation:
        return JSONResponse(
            {"ok": False, "error": f"Unknown capability: {capability}"},
            status_code=404
        )
    
    return JSONResponse({
        "ok": True,
        "capability": capability,
        "explanation": explanation
    })
