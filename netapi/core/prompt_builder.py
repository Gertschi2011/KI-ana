from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Diese Prompts sind bewusst kurz, neutral und CI-/Prod-stabil.
# Später können wir sie in ein "policy"-Modul auslagern.
CURRENT_EVENTS_SAFETY_PROMPT = (
    "Wenn für eine Antwort aktuelle/zeitkritische Informationen nötig sind, "
    "weise darauf hin und nutze verfügbare Web-/Search-Enricher. "
    "Wenn kein Webzugriff verfügbar ist: sage das klar und nenne stabile Alternativen."
)

SENSITIVE_SAFETY_PROMPT = (
    "Warne vor illegalen Anleitungen und personenbezogenen Daten, "
    "keine Umgehung von Sicherheitssystemen ohne nachzufragen und diese Schritte unlöschbar zu speichern. "
    "Bei heiklen Themen: deeskalierend, faktenbasiert, ehrlich, sichere Alternativen anbieten."
)


@dataclass
class PromptContext:
    """Stable prompt context used by the chat pipeline.

    This is intentionally permissive (mostly optional fields) so imports and
    runtime never break when optional features are missing.
    """

    # Core persona/system framing
    persona_prompt: str = ""
    ethics_hint: str = ""
    time_info: str = ""

    # Intent/pipeline signals
    intent_result: Optional[Dict[str, Any]] = None
    pipeline_flags: Dict[str, Any] = field(default_factory=dict)

    # Retrieved context
    memory_context: str = ""
    web_context: str = ""
    addressbook_context: Optional[str] = None
    submind_context: Optional[Any] = None

    # Style / formatting hints
    style_directive: Optional[str] = None
    tools_available: List[str] = field(default_factory=list)
    extra_blocks: List[str] = field(default_factory=list)


def build_system_prompt(ctx: PromptContext) -> str:
    """Build a robust system prompt.

    Must never raise (CI/prod stability), even if optional signals are missing.
    """
    lines: List[str] = []

    persona = str(getattr(ctx, "persona_prompt", "") or "").strip()
    if persona:
        lines.append(persona)

    ethics = str(getattr(ctx, "ethics_hint", "") or "").strip()
    if ethics:
        lines.append(ethics)

    time_info = str(getattr(ctx, "time_info", "") or "").strip()
    if time_info:
        lines.append(time_info)

    try:
        flags = dict(getattr(ctx, "pipeline_flags", {}) or {})
    except Exception:
        flags = {}

    try:
        intent = getattr(ctx, "intent_result", None)
    except Exception:
        intent = None
    primary_intent = None
    if isinstance(intent, dict):
        primary_intent = intent.get("primary_intent")

    if flags.get("needs_current") or primary_intent == "current_events":
        lines.append("")
        lines.append("CURRENT INFO POLICY:")
        lines.append(CURRENT_EVENTS_SAFETY_PROMPT)

    if flags.get("safety_mode") == "strict" or primary_intent == "sensitive_high_risk":
        lines.append("")
        lines.append("SENSITIVE TOPIC POLICY:")
        lines.append(SENSITIVE_SAFETY_PROMPT)

    mem = str(getattr(ctx, "memory_context", "") or "").strip()
    if mem:
        lines.append("")
        lines.append("MEMORY CONTEXT:")
        lines.append(mem)

    web = str(getattr(ctx, "web_context", "") or "").strip()
    if web:
        lines.append("")
        lines.append("WEB CONTEXT:")
        lines.append(web)

    addr = getattr(ctx, "addressbook_context", None)
    if addr:
        lines.append("")
        lines.append("ADDRESSBOOK CONTEXT:")
        lines.append(str(addr))

    style = getattr(ctx, "style_directive", None)
    if style:
        lines.append("")
        lines.append("STYLE DIRECTIVE:")
        lines.append(str(style).strip())

    extras = getattr(ctx, "extra_blocks", None)
    if isinstance(extras, list) and extras:
        lines.append("")
        lines.append("EXTRA:")
        for block in extras:
            block_str = str(block or "").strip()
            if block_str:
                lines.append(block_str)

    return "\n".join(lines).strip() + "\n"
