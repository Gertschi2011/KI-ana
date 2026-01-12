from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

import logging

from netapi.db import SessionLocal, ensure_engine_current
from netapi.models import AuditEvent


logger = logging.getLogger(__name__)


def write_audit_event(
    *,
    actor_type: str,
    actor_id: Optional[int],
    action: str,
    subject_type: str,
    subject_id: Optional[str] = None,
    result: str = "success",
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Append-only audit event writer.

    Intentionally only INSERTs. Any failures are best-effort logged.
    """

    try:
        ensure_engine_current()
        db = SessionLocal()
    except Exception as exc:
        logger.warning("audit_events: failed to open db session: %s", exc)
        return

    try:
        payload = {} if meta is None else dict(meta)
        try:
            event = AuditEvent(
                ts=datetime.utcnow(),
                actor_type=str(actor_type or "system"),
                actor_id=(int(actor_id) if actor_id is not None else None),
                action=str(action or ""),
                subject_type=str(subject_type or ""),
                subject_id=(str(subject_id) if subject_id is not None else None),
                result=str(result or "success"),
                meta=payload,
            )
            db.add(event)
            db.commit()
        except Exception:
            # Backward-compat: some deployments created audit_events.meta as TEXT.
            # Retry once with JSON-serialized string.
            db.rollback()
            event = AuditEvent(
                ts=datetime.utcnow(),
                actor_type=str(actor_type or "system"),
                actor_id=(int(actor_id) if actor_id is not None else None),
                action=str(action or ""),
                subject_type=str(subject_type or ""),
                subject_id=(str(subject_id) if subject_id is not None else None),
                result=str(result or "success"),
                meta=json.dumps(payload, ensure_ascii=False),
            )
            db.add(event)
            db.commit()
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("audit_events: failed to write event (%s): %s", action, exc)
    finally:
        try:
            db.close()
        except Exception:
            pass
