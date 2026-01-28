from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from netapi.deps import get_current_user_opt, get_current_user_required, _effective_plan_id
from netapi import memory_store
from netapi.core import addressbook
from netapi.modules.memory.schemas import UserSourcePrefsBlock
from netapi.modules.memory.schemas import SourceTrustProfileBlock
from netapi.modules.memory.schemas import UserSettingsBlock
from netapi.modules.memory.schemas import InterestProfileBlock
from netapi.modules.memory.schemas import now_iso_z

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
    mode: Optional[str] = None


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
    mode: Optional[str] = None
    preferred_sources: Optional[List[str]] = None
    blocked_sources: Optional[List[str]] = None
    trust_overrides: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    # PR3 trust profile
    domain_stats: Optional[Dict[str, Dict[str, Any]]] = None
    last_asked_at: Optional[str] = None
    last_feedback_at: Optional[str] = None

    # Phase 4 user settings
    proactive_news_enabled: Optional[bool] = None
    proactive_news_schedule: Optional[str] = None
    countries: Optional[List[str]] = None
    langs: Optional[List[str]] = None
    modes: Optional[List[str]] = None

    # Phase 4 interest profile
    category_weights: Optional[Dict[str, float]] = None
    domain_affinity: Optional[Dict[str, float]] = None
    signals_count: Optional[Dict[str, int]] = None
    last_signal_at: Optional[str] = None


def _require_creator_admin(current: Optional[Dict[str, Any]]) -> None:
    if not current:
        raise HTTPException(401, "Authentication required")
    role = str(current.get("role") or "").lower()
    if role not in {"creator", "admin"}:
        raise HTTPException(403, "creator/admin role required")


def _require_transparency_allowed(current: Optional[Dict[str, Any]]) -> None:
    """Allow transparency endpoints for paid users (plan != free) and creator/admin."""
    if not current:
        raise HTTPException(401, "Authentication required")
    role = str(current.get("role") or "").lower()
    roles = current.get("roles")
    roles_norm: set[str] = set()
    if isinstance(roles, (list, tuple)):
        roles_norm = {str(r).lower() for r in roles if r is not None}
    if role in {"creator", "admin"} or ("creator" in roles_norm) or ("admin" in roles_norm):
        return
    plan_id = _effective_plan_id(str(current.get("plan") or "free"))
    if plan_id == "free":
        raise HTTPException(403, "upgrade_required")


class MemoryPreviewRequest(BaseModel):
    ids: List[str] = Field(default_factory=list, max_length=50)
    limit_chars: int = Field(default=240, ge=40, le=2000)


@router.post("/preview")
def memory_preview(body: MemoryPreviewRequest, current=Depends(get_current_user_required)):
    _require_transparency_allowed(current)
    ids = [str(x).strip() for x in (body.ids or []) if str(x or "").strip()]
    ids = ids[:50]
    items: List[Dict[str, Any]] = []
    for bid in ids:
        blk = memory_store.get_block(bid)
        if not isinstance(blk, dict):
            continue
        meta = blk.get("meta") if isinstance(blk.get("meta"), dict) else {}
        content = str(blk.get("content") or "")
        preview = content.strip().replace("\n", " ")
        if len(preview) > int(body.limit_chars or 240):
            preview = preview[: int(body.limit_chars or 240)].rstrip() + "…"
        items.append({
            "id": str(blk.get("id") or bid),
            "ts": int(blk.get("ts") or 0),
            "topic": str(meta.get("topic") or meta.get("topic_path") or ""),
            "title": str(blk.get("title") or ""),
            "preview": preview,
            # keep extra fields for backwards compatibility
            "tags": list(blk.get("tags") or []),
            "url": str(blk.get("url") or ""),
        })
    return {"ok": True, "items": items}


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

        if str(body.type or "").strip().lower() == "source_trust_profile":
            if body.user_id is None or not body.country:
                raise HTTPException(400, "source_trust_profile search requires user_id, country")
            mode = str(body.mode or "news").strip().lower() or "news"
            block_id = addressbook.get_source_trust_profile(
                user_id=int(body.user_id),
                country=str(body.country),
                mode=mode,
            )
            block = memory_store.get_block(block_id) if block_id else None
            return {
                "ok": True,
                "type": "source_trust_profile",
                "user_id": int(body.user_id),
                "country": str(body.country).upper()[:2],
                "mode": mode,
                "block_id": block_id,
                "block": block,
            }

        if str(body.type or "").strip().lower() == "user_settings":
            if body.user_id is None:
                raise HTTPException(400, "user_settings search requires user_id")
            block_id = addressbook.get_user_settings(user_id=int(body.user_id))
            block = memory_store.get_block(block_id) if block_id else None
            return {
                "ok": True,
                "type": "user_settings",
                "user_id": int(body.user_id),
                "block_id": block_id,
                "block": block,
            }

        if str(body.type or "").strip().lower() == "interest_profile":
            if body.user_id is None or not body.country or not body.lang:
                raise HTTPException(400, "interest_profile search requires user_id, country, lang")
            mode = str(body.mode or "news").strip().lower() or "news"
            block_id = addressbook.get_interest_profile(
                user_id=int(body.user_id),
                country=str(body.country),
                lang=str(body.lang),
                mode=mode,
            )
            block = memory_store.get_block(block_id) if block_id else None
            return {
                "ok": True,
                "type": "interest_profile",
                "user_id": int(body.user_id),
                "country": str(body.country).upper()[:2],
                "lang": str(body.lang).lower(),
                "mode": mode,
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

        if str(body.type or "").strip().lower() == "source_trust_profile":
            if body.user_id is None or not body.country:
                raise HTTPException(400, "source_trust_profile store requires user_id, country")

            profile = SourceTrustProfileBlock(
                user_id=int(body.user_id),
                country=str(body.country),
                mode=str(body.mode or "news"),
                domain_stats=dict(body.domain_stats or {}),
                updated_at=None,
                last_asked_at=body.last_asked_at,
                last_feedback_at=body.last_feedback_at,
            ).normalized()

            now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
            profile = profile.copy(update={"updated_at": now})

            tags = [
                "source_trust_profile",
                "trust:sources",
                f"user:{profile.user_id}",
                f"country:{profile.country}",
                f"mode:{profile.mode}",
            ]
            for dom in list((profile.domain_stats or {}).keys())[:25]:
                tags.append(f"dom:{dom}")

            title = f"Source Trust: user={profile.user_id} {profile.country} {profile.mode}"
            content = json.dumps(profile.dict(), ensure_ascii=False, indent=2)
            meta = profile.dict()
            meta["type"] = "source_trust_profile"

            block_id = memory_store.add_block(
                title=title,
                content=content,
                tags=tags,
                url=body.url,
                meta=meta,
            )

            addressbook.index_source_trust_profile(
                block_id=block_id,
                user_id=profile.user_id,
                country=profile.country,
                mode=profile.mode,
                domain_count=len(profile.domain_stats or {}),
                updated_at=profile.updated_at,
            )

            return {"ok": True, "id": block_id, "type": "source_trust_profile"}

        if str(body.type or "").strip().lower() == "user_settings":
            if body.user_id is None:
                raise HTTPException(400, "user_settings store requires user_id")

            settings = UserSettingsBlock(
                user_id=int(body.user_id),
                proactive_news_enabled=bool(body.proactive_news_enabled) if body.proactive_news_enabled is not None else False,
                proactive_news_schedule=body.proactive_news_schedule,
                countries=list(body.countries or ["AT"]),
                langs=list(body.langs or ["de"]),
                modes=list(body.modes or ["news"]),
            ).normalized()

            now = now_iso_z()
            settings = settings.copy(update={"updated_at": now})
            meta = settings.dict()

            tags = [
                "user_settings",
                f"user:{settings.user_id}",
            ]
            title = f"User Settings: user={settings.user_id}"
            content = json.dumps(meta, ensure_ascii=False, indent=2)

            block_id = memory_store.add_block(
                title=title,
                content=content,
                tags=tags,
                url=body.url,
                meta=meta,
            )
            addressbook.index_user_settings(
                block_id=block_id,
                user_id=settings.user_id,
                proactive_news_enabled=bool(settings.proactive_news_enabled),
                updated_at=settings.updated_at,
            )
            return {"ok": True, "id": block_id, "type": "user_settings"}

        if str(body.type or "").strip().lower() == "interest_profile":
            if body.user_id is None or not body.country or not body.lang:
                raise HTTPException(400, "interest_profile store requires user_id, country, lang")
            mode = str(body.mode or "news").strip().lower() or "news"

            profile = InterestProfileBlock(
                user_id=int(body.user_id),
                country=str(body.country),
                lang=str(body.lang),
                mode=mode,
                category_weights=dict(body.category_weights or {}),
                domain_affinity=dict(body.domain_affinity or {}),
                signals_count=dict(body.signals_count or {}),
                last_signal_at=body.last_signal_at,
            ).normalized()

            now = now_iso_z()
            profile = profile.copy(update={"updated_at": now})
            meta = profile.dict()

            tags = [
                "interest_profile",
                "interest:news",
                f"user:{profile.user_id}",
                f"country:{profile.country}",
                f"lang:{profile.lang}",
                f"mode:{profile.mode}",
            ]
            for dom in list((profile.domain_affinity or {}).keys())[:20]:
                tags.append(f"dom:{dom}")
            for cat in list((profile.category_weights or {}).keys())[:20]:
                tags.append(f"cat:{cat}")

            title = f"Interest Profile: user={profile.user_id} {profile.country} {profile.lang} {profile.mode}"
            content = json.dumps(meta, ensure_ascii=False, indent=2)

            block_id = memory_store.add_block(
                title=title,
                content=content,
                tags=tags,
                url=body.url,
                meta=meta,
            )
            addressbook.index_interest_profile(
                block_id=block_id,
                user_id=profile.user_id,
                country=profile.country,
                lang=profile.lang,
                mode=profile.mode,
                updated_at=profile.updated_at,
            )
            return {"ok": True, "id": block_id, "type": "interest_profile"}

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
