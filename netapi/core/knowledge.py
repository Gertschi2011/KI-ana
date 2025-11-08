from __future__ import annotations
from typing import Optional
import logging
import traceback

logger = logging.getLogger(__name__)

try:
    from netapi import memory_store as _mem  # type: ignore
except Exception:
    _mem = None  # type: ignore


def process_user_teaching(user_msg: str, topic_path: Optional[str], state) -> str:
    """Create a short-term learning block from a user's explanation and index it.

    Returns a friendly confirmation reply text.
    """
    topic = (topic_path or "Unsortiert/UserWissen").strip()
    msg = (user_msg or "").strip()
    block_id = None
    try:
        if _mem is None:
            raise RuntimeError("memory module not initialized")
        if not msg:
            raise RuntimeError("empty user message for teaching")
        block_id = _mem.create_short_term_block(
            topic_path=topic,
            info=msg,
            source="user",
            confidence=0.6,
        )
        try:
            if hasattr(_mem, "index_topic") and block_id:
                _mem.index_topic(topic, block_id)
        except Exception as _e:
            logger.warning("index_topic failed for %s", topic, exc_info=True)
    except Exception as e:
        logger.error("process_user_teaching failed: %s", e)
        try:
            logger.debug(traceback.format_exc())
        except Exception:
            pass

    # Build user reply regardless of storage outcome
    if block_id:
        extra = " Ich versuche mir das als kleinen Wissensblock zu merken."
    else:
        extra = " Ich konnte das zwar nicht speichern, aber ich behalte es im Kopf."

    return (
        "Danke, das hilft mir sehr. "
        f"Ich merke mir '{topic}' jetzt so:\n\n{msg}" + extra
    )
