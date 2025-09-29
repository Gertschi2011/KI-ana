from __future__ import annotations
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any, Dict

router = APIRouter(prefix="/api/reflection", tags=["reflection"])

BASE_DIR = Path.home() / "ki_ana"
REFLECT_PATH = BASE_DIR / "system" / "reflection_engine.py"
THOUGHT_LOGGER_PATH = BASE_DIR / "system" / "thought_logger.py"


def _load_reflector():
    return SourceFileLoader("reflection_engine", str(REFLECT_PATH)).load_module()  # type: ignore


def _load_thought_logger():
    return SourceFileLoader("thought_logger", str(THOUGHT_LOGGER_PATH)).load_module()  # type: ignore


@router.post("/reflect")
async def reflect_topic(topic: str):
    """Reflect across blocks for a given topic and return insights/corrections."""
    if not topic or not topic.strip():
        raise HTTPException(400, "missing topic")
    mod = _load_reflector()
    if not hasattr(mod, "reflect_blocks_by_topic"):
        raise HTTPException(503, "reflection engine not available")
    # For now, let the engine gather blocks via the viewer endpoint is not ideal; we pass empty list
    # The engine method expects pre-filtered blocks; here we provide just topic for heuristic.
    try:
        res: Dict[str, Any] = mod.reflect_blocks_by_topic(topic, [])  # type: ignore
        _tl = _load_thought_logger()
        try:
            _tl.log_decision(component="reflection", action="reflect", input_ref=topic, outcome="ok", reasons="manual_api_trigger")  # type: ignore
        except Exception:
            pass
        return JSONResponse(res)
    except Exception as e:
        raise HTTPException(500, f"reflect failed: {e}")


@router.post("/reflect/block")
async def reflect_single_block(block_id: str = Body(..., embed=True)):
    """Placeholder endpoint to reflect on a specific block by id; returns stub until detailed design."""
    if not block_id:
        raise HTTPException(400, "missing block_id")
    _tl = _load_thought_logger()
    try:
        _tl.log_decision(component="reflection", action="reflect_block", input_ref=block_id, outcome="ok", reasons="manual_api_trigger")  # type: ignore
    except Exception:
        pass
    # Future: load block, analyze contradictions across related topic
    return {"ok": True, "block_id": block_id, "insights": "not implemented fully yet"}


@router.post("/reflect/topic/{topic}")
async def reflect_topic_ollama(topic: str):
    """Trigger local reflection using Ollama and persist a signed reflection block."""
    t = (topic or "").strip()
    if not t:
        raise HTTPException(400, "missing topic")
    engine = _load_reflector()
    if not hasattr(engine, "reflect_on_topic"):
        raise HTTPException(503, "reflect_on_topic not available")
    try:
        res = engine.reflect_on_topic(t)  # type: ignore
        if not res.get("ok"):
            raise HTTPException(502, f"reflection failed: {res.get('reason')}")
        return {"status": "ok", "block_id": res.get("id"), "path": res.get("path")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"reflect_on_topic error: {e}")
