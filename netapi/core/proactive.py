"""Phase 4: Proactive hook skeleton (no scheduler).

This module is intentionally minimal:
- It defines the contract for future proactive triggers.
- It does NOT run any background jobs or send notifications.

The only supported behavior in Phase 4 is storing user opt-in settings
(`user_settings` blocks). Any actual proactive delivery is out of scope.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def should_send_proactive_news(*, user_settings: Optional[Dict[str, Any]]) -> bool:
    """Return True if a proactive news run would be allowed.

    Phase 4 policy:
    - Never proactive without explicit opt-in stored in user_settings.
    """
    if not isinstance(user_settings, dict):
        return False
    return bool(user_settings.get("proactive_news_enabled"))


def build_proactive_news_job(*, user_id: int, user_settings: Dict[str, Any]) -> Dict[str, Any]:
    """Build a declarative job payload.

    The caller may enqueue/execute it in the future. In Phase 4 we only return
    a dict and do not run anything.
    """
    return {
        "type": "proactive_news_job",
        "user_id": int(user_id),
        "schedule": user_settings.get("proactive_news_schedule"),
        "countries": user_settings.get("countries") or [],
        "langs": user_settings.get("langs") or [],
        "modes": user_settings.get("modes") or ["news"],
    }
