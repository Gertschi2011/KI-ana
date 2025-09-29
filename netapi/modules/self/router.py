from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pathlib import Path
from importlib.machinery import SourceFileLoader
import json

router = APIRouter(prefix="/self", tags=["self"]) 
BASE_DIR = Path.home() / "ki_ana"
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
