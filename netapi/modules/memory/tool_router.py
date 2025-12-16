from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from netapi.deps import get_current_user_opt
from netapi import memory_store
from netapi.core import addressbook
from netapi.modules.memory.schemas import UserSourcePrefsBlock

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory-tools"])


class MemorySearchRequest(BaseModel):
    query: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=50)
    type: Optional[str] = None
    user_id: Optional[int] = None
    country: Optional[str] = None
    lang: Optional[str] = None
    intent: Optional[str] = None


class MemoryStoreRequest(BaseModel):
    # Legacy/generic blocks
    title: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    url: Optional[str] = None

    # Typed blocks (PR2)
    type: Optional[str] = None
    user_id: Optional[int] = None
    country: Optional[str] = None
    lang: Optional[str] = None
    intent: Optional[str] = None
    preferred_sources: Optional[List[str]] = None
    blocked_sources: Optional[List[str]] = None
    trust_overrides: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


def _require_creator_admin(current: Optional[Dict[str, Any]]) -> None:
    if not current:
        raise HTTPException(401, "Authentication required")
    role = str(current.get("role") or "").lower()
    if role not in {"creator", "admin"}:
        raise HTTPException(403, "creator/admin role required")


@router.post("/search")
def memory_search(body: MemorySearchRequest, current=Depends(get_current_user_opt)):
    _require_creator_admin(current)
    try:
        if str(body.type or "").strip().lower() == "user_source_prefs":
            if body.user_id is None or not body.country or not body.lang:
                raise HTTPException(400, "user_source_prefs search requires user_id, country, lang")
            intent = str(body.intent or "news").strip().lower() or "news"
            block_id = addressbook.get_source_prefs(
                user_id=int(body.user_id),
                country=str(body.country),
                lang=str(body.lang),
                intent=intent,
            )
            block = memory_store.get_block(block_id) if block_id else None
            return {
                "ok": True,
                "type": "user_source_prefs",
                "user_id": int(body.user_id),
                "country": str(body.country).upper()[:2],
                "lang": str(body.lang).lower(),
                "intent": intent,
                "block_id": block_id,
                "block": block,
            }

        q = (body.query or "").strip()
        if not q:
            raise HTTPException(400, "query is required")
        hits = memory_store.search_blocks(q, top_k=int(body.limit))
        results: List[Dict[str, Any]] = []
        for bid, score in hits:
            results.append({"id": bid, "score": score, "block": memory_store.get_block(bid)})
        return {"ok": True, "query": q, "results": results}
    except Exception as exc:
        raise HTTPException(500, f"memory search failed: {exc}") from exc


@router.post("/store")
def memory_store_block(body: MemoryStoreRequest, current=Depends(get_current_user_opt)):
    _require_creator_admin(current)
    try:
        if str(body.type or "").strip().lower() == "user_source_prefs":
            if body.user_id is None or not body.country or not body.lang:
                raise HTTPException(400, "user_source_prefs store requires user_id, country, lang")

            prefs = UserSourcePrefsBlock(
                user_id=int(body.user_id),
                country=str(body.country),
                lang=str(body.lang),
                intent=str(body.intent or "news"),
                preferred_sources=list(body.preferred_sources or []),
                blocked_sources=list(body.blocked_sources or []),
                trust_overrides=body.trust_overrides,
                notes=body.notes,
            ).normalized()

            now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
            prefs = prefs.copy(update={"created_at": now, "updated_at": now})

            tags = [
                "user_source_prefs",
                "prefs:sources",
                f"user:{prefs.user_id}",
                f"country:{prefs.country}",
                f"lang:{prefs.lang}",
                f"intent:{prefs.intent}",
            ]
            tags.extend([f"pref:{d}" for d in (prefs.preferred_sources or [])])
            tags.extend([f"block:{d}" for d in (prefs.blocked_sources or [])])

            title = f"Source Prefs: user={prefs.user_id} {prefs.country} {prefs.lang} {prefs.intent}"
            content = json.dumps(prefs.dict(), ensure_ascii=False, indent=2)
            meta = prefs.dict()
            meta["type"] = "user_source_prefs"

            block_id = memory_store.add_block(
                title=title,
                content=content,
                tags=tags,
                url=body.url,
                meta=meta,
            )

            addressbook.index_source_prefs(
                block_id=block_id,
                user_id=prefs.user_id,
                country=prefs.country,
                lang=prefs.lang,
                intent=prefs.intent,
                preferred=prefs.preferred_sources,
                blocked=prefs.blocked_sources,
                trust_overrides=prefs.trust_overrides,
                updated_at=prefs.updated_at,
            )

            return {"ok": True, "id": block_id, "type": "user_source_prefs"}

        if not body.title or not str(body.title).strip() or not body.content or not str(body.content).strip():
            raise HTTPException(400, "title and content are required")

        block_id = memory_store.add_block(
            title=str(body.title).strip(),
            content=str(body.content).strip(),
            tags=body.tags or [],
            url=body.url,
        )
        return {"ok": True, "id": block_id}
    except Exception as exc:
        raise HTTPException(500, f"memory store failed: {exc}") from exc
