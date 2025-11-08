from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from .state import add_learning_item


def now_iso() -> str:
    try:
        return datetime.now(timezone.utc).isoformat()
    except Exception:
        from datetime import datetime as _dt
        return _dt.utcnow().isoformat() + "Z"


def decide_ask_or_search(user_msg: str, state, persona) -> str:
    """
    Returns 'ask_user', 'web_search' or ''.
    Simple heuristic:
      - If explicitly asking for explanation/definition -> web_search
      - Otherwise ask user first (childlike)
    """
    try:
        t = (user_msg or "").lower()
        # Lern-/Erklär-Trigger
        if any(p in t for p in ["erklär mir", "erkläre mir", "kannst du mir erklären"]):
            return "web_search"
        if any(p in t for p in ["was ist", "was weißt du über", "was weisst du über"]):
            return "web_search"
    except Exception:
        pass
    return "ask_user"


def build_childlike_question(user_msg: str, persona, state) -> str:
    return (
        "Das weiß ich noch nicht so gut. "
        "Magst du mir kurz mit deinen eigenen Worten erklären, worum es dabei geht? "
        "Ich versuche es mir zu merken."
    )


def record_user_teaching(state, topic: str, fact: str) -> None:
    add_learning_item(state, topic=topic or "unbekanntes Thema", fact=fact or "", source="user", ts=now_iso())
    try:
        state.pending_followup = None
    except Exception:
        pass
