from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from importlib.machinery import SourceFileLoader
from pathlib import Path

BASE_DIR = Path.home() / "ki_ana"
UTILS_PATH = BASE_DIR / "system" / "block_utils.py"

_utils = SourceFileLoader("block_utils", str(UTILS_PATH)).load_module()  # type: ignore

router = APIRouter(prefix="/blocks", tags=["blocks"])


@router.get("")
def list_blocks(topic: Optional[str] = None,
               tags: Optional[str] = Query(None, description="Comma-separated tags"),
               hash: Optional[str] = Query(None, alias="hash"),
               limit: int = 200):
    tag_list: List[str] = []
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    blocks = _utils.query_blocks(topic=topic, tags=tag_list, content_hash=hash, limit=limit)  # type: ignore
    # verify signatures before returning
    out = []
    for b in blocks:
        ok, _ = _utils.verify_signature(b)  # type: ignore
        if ok:
            out.append(b)
    return {"ok": True, "count": len(out), "items": out}


@router.get("/{block_id}")
def get_block(block_id: str):
    obj, reason = _utils.load_block_by_id(block_id, verify=True)  # type: ignore
    if not obj:
        raise HTTPException(status_code=404, detail=reason)
    return obj
