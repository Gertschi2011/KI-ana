"""Lightweight helpers for recording TimeFlow timeline events."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ...models import TimeflowEvent


def record_timeflow_event(
    db: Session,
    *,
    user_id: int,
    event_type: str,
    meta: Optional[Dict[str, Any]] = None,
    auto_commit: bool = False,
) -> None:
    """Persist a new TimeFlow event for a user."""
    if not user_id or not event_type:
        return
    try:
        payload = TimeflowEvent(
            user_id=int(user_id),
            event_type=str(event_type)[:64],
            created_at=int(time.time()),
            meta=json.dumps(meta or {}, ensure_ascii=False),
        )
        db.add(payload)
        if auto_commit:
            db.commit()
    except Exception:
        # Roll back only the event insert to keep parent transaction healthy.
        try:
            db.rollback()
        except Exception:
            pass


def _safe_load_meta(meta_raw: str | None) -> Dict[str, Any]:
    if not meta_raw:
        return {}
    try:
        return json.loads(meta_raw)
    except Exception:
        return {}


def serialize_timeflow_event(row: TimeflowEvent) -> Dict[str, Any]:
    """Return an API-friendly dict for a TimeflowEvent row."""
    return {
        "id": int(getattr(row, "id", 0) or 0),
        "user_id": int(getattr(row, "user_id", 0) or 0),
        "event_type": getattr(row, "event_type", "generic"),
        "created_at": int(getattr(row, "created_at", 0) or 0),
        "meta": _safe_load_meta(getattr(row, "meta", None)),
    }


def record_ethics_hint_event(*args, **kwargs):
    """Stub for optional ethics hint event recording (used by clean_router)."""
    return None
