from __future__ import annotations

import os
import time
from typing import Any, Dict

from sqlalchemy import func
from sqlalchemy.sql import and_, or_

from backend.workers.celery_app import celery

from netapi.audit_events import write_audit_event
from netapi.db import SessionLocal, ensure_engine_current, init_db
from netapi.models import Conversation, Message

@celery.task(name="ingest.parse_file")
def task_parse_file(obj_key: str) -> dict:
    # Scaffold implementation
    return {"ok": True, "object": obj_key, "parsed": True}

@celery.task(name="embed.text")
def task_embed_text(text: str) -> dict:
    # Scaffold embedding (returns dummy vector)
    return {"ok": True, "vector": [0.1, 0.2, 0.3]}


@celery.task(name="maintenance.retention_purge")
def task_retention_purge() -> Dict[str, Any]:
    """D2: Enforce retention policy (safe-by-default).

    - Purges chat conversations/messages older than RETENTION_CHAT_DAYS (default 30)
    - Optional dry-run: RETENTION_DRY_RUN=1

    Each run emits an append-only audit event (audit_events): action=RETENTION_PURGE.
    """

    now_ts = int(time.time())
    try:
        days = int(str(os.getenv("RETENTION_CHAT_DAYS", "30")).strip() or "30")
    except Exception:
        days = 30
    days = max(1, min(3650, int(days)))

    dry_run = str(os.getenv("RETENTION_DRY_RUN", "0")).strip() == "1"
    cutoff_ts = int(now_ts - (days * 86400))

    ensure_engine_current()
    # Worker containers don't run FastAPI startup; ensure tables exist.
    try:
        init_db()
    except Exception:
        pass
    db = SessionLocal()
    deleted_messages = 0
    deleted_conversations = 0

    try:
        subq = (
            db.query(
                Message.conv_id.label("conv_id"),
                func.max(Message.created_at).label("last_msg_ts"),
            )
            .group_by(Message.conv_id)
            .subquery()
        )

        eligible_q = (
            db.query(Conversation.id)
            .outerjoin(subq, Conversation.id == subq.c.conv_id)
            .filter(
                or_(
                    and_(subq.c.last_msg_ts.isnot(None), subq.c.last_msg_ts < cutoff_ts),
                    and_(subq.c.last_msg_ts.is_(None), Conversation.created_at < cutoff_ts),
                )
            )
        )

        eligible_ids = [int(r[0]) for r in (eligible_q.all() or [])]

        if not eligible_ids:
            payload = {
                "ok": True,
                "dry_run": dry_run,
                "chat_days": days,
                "cutoff_ts": cutoff_ts,
                "eligible_conversations": 0,
                "deleted_conversations": 0,
                "deleted_messages": 0,
            }
            write_audit_event(
                actor_type="system",
                actor_id=None,
                action="RETENTION_PURGE",
                subject_type="chat",
                subject_id=None,
                result="success",
                meta=payload,
            )
            return payload

        # Count messages in eligible conversations
        msg_count = (
            db.query(func.count(Message.id))
            .filter(Message.conv_id.in_(eligible_ids))
            .scalar()
            or 0
        )

        if not dry_run:
            deleted_messages = int(
                db.query(Message)
                .filter(Message.conv_id.in_(eligible_ids))
                .delete(synchronize_session=False)
                or 0
            )
            deleted_conversations = int(
                db.query(Conversation)
                .filter(Conversation.id.in_(eligible_ids))
                .delete(synchronize_session=False)
                or 0
            )
            db.commit()

        payload = {
            "ok": True,
            "dry_run": dry_run,
            "chat_days": days,
            "cutoff_ts": cutoff_ts,
            "eligible_conversations": int(len(eligible_ids)),
            "candidate_messages": int(msg_count),
            "deleted_conversations": int(0 if dry_run else deleted_conversations),
            "deleted_messages": int(0 if dry_run else deleted_messages),
            "orphan_vectors_deleted": 0,
            "orphan_blobs_deleted": 0,
        }

        write_audit_event(
            actor_type="system",
            actor_id=None,
            action="RETENTION_PURGE",
            subject_type="chat",
            subject_id=None,
            result="success",
            meta=payload,
        )
        return payload

    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        write_audit_event(
            actor_type="system",
            actor_id=None,
            action="RETENTION_PURGE",
            subject_type="chat",
            subject_id=None,
            result="error",
            meta={"error": f"{type(exc).__name__}: {exc}", "chat_days": days, "cutoff_ts": cutoff_ts, "dry_run": dry_run},
        )
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass
