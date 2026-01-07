from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class IntentResult:
    """Lightweight intent classification result.

    The chat v2 router uses this for tagging and pipeline flagging.
    This implementation is intentionally minimal to avoid optional
    dependency failures during CI / TEST_MODE runs.
    """

    primary_intent: Optional[str] = None
    secondary_intents: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_intent": self.primary_intent,
            "secondary_intents": list(self.secondary_intents),
        }


def detect_intents(message: str) -> IntentResult:
    """Best-effort intent detection.

    Keep heuristics simple and dependency-free.
    """

    text = (message or "").strip().lower()
    if not text:
        return IntentResult()

    secondary: List[str] = []
    primary: Optional[str] = None

    # Minimal current-events heuristic used by chat v2.
    if any(token in text for token in ("news", "nachrichten", "aktuell", "heute", "current")):
        primary = "current_events"

    # Basic web/search hint.
    if any(token in text for token in ("http://", "https://", "quelle", "source", "link")):
        secondary.append("web")

    return IntentResult(primary_intent=primary, secondary_intents=secondary)


def apply_intent_to_pipeline(
    intent_result: IntentResult,
    pipeline_flags: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply intent-derived flags to the pipeline flags dict."""

    flags: Dict[str, Any] = dict(pipeline_flags or {})

    tags = []
    if intent_result.primary_intent:
        tags.append(intent_result.primary_intent)
    tags.extend([t for t in intent_result.secondary_intents if t])

    if tags:
        flags.setdefault("intent_tags", tags)

    if intent_result.primary_intent == "current_events" or "current_events" in intent_result.secondary_intents:
        flags.setdefault("is_news", True)

    return flags
