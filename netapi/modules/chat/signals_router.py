from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from netapi.deps import get_current_user_opt, get_db
from netapi.modules.memory.schemas import InterestProfileBlock, now_iso_z
from netapi.modules.memory.schemas import normalize_domain

try:
    from netapi import memory_store as _memory_store  # type: ignore
except Exception:  # pragma: no cover
    _memory_store = None  # type: ignore

router = APIRouter(tags=["chat-v2-signals"])


def _debug_allowed() -> bool:
    env_value = (os.getenv("KIANA_ENV") or os.getenv("ENV") or "dev").lower()
    if env_value in {"dev", "development", "test", "testing"}:
        return True
    override = (os.getenv("PROMPT_DEBUG_PREVIEW") or "").strip().lower()
    return override in {"1", "true", "yes", "on"}


class ChatSignalRequest(BaseModel):
    user_id: int
    country: str = Field(min_length=2, max_length=2)
    lang: str = Field(min_length=2, max_length=12)
    mode: str = Field(default="news")
    signal_type: str = Field(min_length=1)
    domain: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None


@router.post("/signal")
async def chat_signal(
    body: ChatSignalRequest,
    current=Depends(get_current_user_opt),
    db=Depends(get_db),
):
    # Auth: creator/admin; allow unauth only in dev/test.
    if current:
        if str(current.get("role") or "").lower() not in {"creator", "admin"}:
            raise HTTPException(403, "signal requires creator/admin role")
    else:
        if not _debug_allowed():
            raise HTTPException(404, "signal is not available in this environment")

    if _memory_store is None:
        raise HTTPException(500, "memory_store not available")

    from netapi.core import addressbook
    from netapi.core.interest_profile import apply_interest_signal

    uid = int(body.user_id)
    country = str(body.country).strip().upper()[:2]
    lang = str(body.lang).strip().lower()
    mode = str(body.mode or "news").strip().lower() or "news"

    dom = normalize_domain(body.domain or body.url or "")
    cat = str(body.category or "").strip().lower() or None

    existing_bid = addressbook.get_interest_profile(user_id=uid, country=country, lang=lang, mode=mode)
    existing = None
    if existing_bid:
        try:
            blk = _memory_store.get_block(existing_bid)
            if isinstance(blk, dict):
                existing = blk.get("meta") or blk
        except Exception:
            existing = None

    base_profile = existing if isinstance(existing, dict) else {
        "type": "interest_profile",
        "user_id": uid,
        "country": country,
        "lang": lang,
        "mode": mode,
        "category_weights": {},
        "domain_affinity": {},
        "signals_count": {},
        "last_signal_at": None,
        "updated_at": None,
    }

    updated_meta, _delta = apply_interest_signal(
        base_profile,
        signal_type=body.signal_type,
        domain=dom,
        category=cat,
    )

    updated_meta["type"] = "interest_profile"
    updated_meta["user_id"] = uid
    updated_meta["country"] = country
    updated_meta["lang"] = lang
    updated_meta["mode"] = mode
    updated_meta["last_signal_at"] = now_iso_z()
    updated_meta["updated_at"] = now_iso_z()

    # Validate/normalize through schema.
    profile = InterestProfileBlock(**updated_meta).normalized()
    meta = profile.dict()

    title = f"Interest Profile: user={uid} {country} {lang} {mode}"
    content = json.dumps(meta, ensure_ascii=False, indent=2)
    tags = [
        "interest_profile",
        "interest:news",
        f"user:{uid}",
        f"country:{country}",
        f"lang:{lang}",
        f"mode:{mode}",
    ]

    block_id = _memory_store.add_block(title=title, content=content, tags=tags, meta=meta)
    addressbook.index_interest_profile(
        block_id=block_id,
        user_id=uid,
        country=country,
        lang=lang,
        mode=mode,
        updated_at=meta.get("updated_at"),
    )

    return {"ok": True, "id": block_id, "type": "interest_profile", "profile": meta}
