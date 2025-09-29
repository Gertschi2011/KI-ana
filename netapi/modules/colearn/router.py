from __future__ import annotations
from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import JSONResponse
from typing import Any, Dict, Optional
from pathlib import Path
import json

router = APIRouter(prefix="/colearn", tags=["colearn"])
BASE_DIR = Path.home() / "ki_ana"

# Optional modules
try:
    from netapi import memory_store as _mem
except Exception:
    _mem = None  # type: ignore

try:
    from netapi.core import llm_local as _llm
except Exception:
    _llm = None  # type: ignore

try:
    from importlib.machinery import SourceFileLoader
    REFLECT_PATH = BASE_DIR / "system" / "reflection_engine.py"
    _reflect = SourceFileLoader("reflection_engine", str(REFLECT_PATH)).load_module() if REFLECT_PATH.exists() else None  # type: ignore
except Exception:
    _reflect = None  # type: ignore

try:
    from system.thought_logger import log_decision  # type: ignore
except Exception:
    def log_decision(**kwargs):
        pass


def _paraphrase(text: str) -> str:
    if _llm and getattr(_llm, "available", lambda: False)():
        prompt = (
            "Ich erkläre dir etwas Neues – merk es dir und gib es in deinen Worten wieder. "
            "Fasse kurz, präzise, neutral zusammen.\n\n" + text[:2000]
        )
        out = _llm.chat_once(user=prompt, system="Du bist KI_ana. Paraphrasiere kurz und präzise in eigenen Worten.")
        return (out or "").strip()
    return (text[:280] + ("…" if len(text) > 280 else "")).strip()


@router.post("/teach")
async def teach(payload: Dict[str, Any] = Body(...)):
    if not isinstance(payload, dict):
        raise HTTPException(400, "invalid body")
    title = (payload.get("title") or "").strip()
    content = (payload.get("content") or "").strip()
    topic = (payload.get("topic") or title or (content.splitlines()[0][:60] if content else "Lehre")).strip()
    tags = payload.get("tags") or []
    if not content:
        raise HTTPException(400, "missing content")
    if _mem is None:
        raise HTTPException(500, "memory_store not available")
    meta = {
        "provenance": "user_teach",
        "teacher": payload.get("teacher") or "",
        "reflection": (payload.get("reflection") or "").strip(),
    }
    bid = _mem.add_block(title=title or topic, content=content, tags=tags, url=payload.get("url"), meta=meta)
    summary = _paraphrase(content)
    log_decision(component="co_learn", action="teach", outcome="saved", reasons=["user teaching"], meta={"block_id": bid, "topic": topic})
    return JSONResponse({"ok": True, "id": bid, "topic": topic, "paraphrase": summary})


@router.post("/feedback/rate")
async def rate(payload: Dict[str, Any] = Body(...)):
    if _mem is None:
        raise HTTPException(500, "memory_store not available")
    bid = (payload.get("block_id") or "").strip()
    if not bid:
        raise HTTPException(400, "missing block_id")
    score = float(payload.get("score", 0.0))
    comment = (payload.get("comment") or "").strip()
    proof_url = (payload.get("proof_url") or "").strip()
    rec = _mem.rate_block(bid, score, proof_url=proof_url, reviewer=payload.get("reviewer"), comment=comment)
    log_decision(component="co_learn", action="rate", outcome="ok", reasons=["user feedback"], meta={"block_id": bid, "score": score})
    return JSONResponse({"ok": True, **rec})


@router.get("/gaps")
async def gaps(topic: str = Query(..., min_length=1)):
    t = (topic or "").strip()
    # Use reflection over blocks to find gaps
    if _reflect and hasattr(_reflect, "reflect_blocks_by_topic"):
        blocks = []
        try:
            mem_dir = BASE_DIR / "memory" / "long_term" / "blocks"
            for p in mem_dir.glob("*.json"):
                try:
                    blocks.append(json.loads(p.read_text(encoding="utf-8")))
                except Exception:
                    continue
        except Exception:
            pass
        res = _reflect.reflect_blocks_by_topic(t, blocks)  # type: ignore
        log_decision(component="co_learn", action="gaps", outcome="ok", reasons=["reflect gaps"], meta={"topic": t})
        return JSONResponse({"ok": True, **res})
    return JSONResponse({"ok": True, "topic": t, "insights": "Keine Reflexion verfügbar", "corrections": []})
