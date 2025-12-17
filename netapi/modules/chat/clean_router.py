"""
Clean Chat Router - New Architecture

This is the NEW chat endpoint using the simplified, self-reflecting pipeline.
Runs parallel to the old router for comparison and gradual migration.

Endpoint: POST /api/v2/chat

Key Differences from old router:
1. No complex formatters or templates
2. Direct LLM answers with self-reflection
3. Clean, maintainable code
4. Proper logging and metrics
5. Part of the vision for autonomous AI

Migration Plan:
- Phase 1: Run parallel, A/B test
- Phase 2: Migrate users gradually
- Phase 3: Replace old router completely
"""

from __future__ import annotations
import json
import logging
import os
import re
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable, Tuple
from fastapi import APIRouter, Request, Depends, HTTPException
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR
from pydantic import BaseModel, Field

from netapi.deps import get_current_user_opt, get_db
from netapi.core.addressbook_boost import (
    AddressBookEntrySnapshot,
    load_boost_blocks,
    match_entry_for_prompt,
    summarize_blocks_for_prompt,
)
from netapi.core.response_pipeline import PipelineContext, PipelineResponse
from netapi.core.reflector import get_reflector, ResponseReflector
from netapi.core.web_enricher import WebEnricher
from netapi.core import ethics_eval
from netapi.learning.hub import get_learning_hub
from netapi.core.intent_engine import (
    IntentResult,
    apply_intent_to_pipeline,
    detect_intents,
)
from netapi.core.prompt_builder import (
    CURRENT_EVENTS_SAFETY_PROMPT,
    PromptContext,
    SENSITIVE_SAFETY_PROMPT,
    build_system_prompt,
)
from netapi.modules.chat.current_detection import needs_current_info
from netapi.modules.timeflow.events import record_ethics_hint_event
from netapi.modules.user.context import build_user_locale_from_user

try:
    from netapi import memory_store as _memory_store  # type: ignore
except Exception:  # pragma: no cover
    _memory_store = None  # type: ignore

try:
    from netapi.modules.explain import get_enricher  # type: ignore
except Exception:  # pragma: no cover
    get_enricher = None  # type: ignore

try:
    from netapi.modules.admin.router import write_audit  # type: ignore
except Exception:  # pragma: no cover
    write_audit = None  # type: ignore

# Import existing tools
try:
    from netapi.agent.tools import tool_memory_search  # type: ignore
except ImportError:  # pragma: no cover - development fallback
    def tool_memory_search(q: str, top_k: int = 3) -> tuple:
        return [], []


router = APIRouter(prefix="/api/v2/chat", tags=["chat-v2"])
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Phase 4: Mount signal endpoint router under /api/v2/chat
try:
    from netapi.modules.chat.signals_router import router as _signals_router  # type: ignore

    router.include_router(_signals_router)
except Exception:
    _signals_router = None  # type: ignore



class ChatRequest(BaseModel):
    message: str
    persona: str = "helpful"
    lang: str = "de"
    enable_reflection: bool = True
    quality_threshold: float = 0.7
    conv_id: Optional[int] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    style: Optional[str] = None
    bullets: Optional[int] = None
    logic: Optional[str] = None
    format: Optional[str] = None
    web_ok: Optional[bool] = None
    autonomy: Optional[int] = None


class ChatResponse(BaseModel):
    ok: bool
    reply: str
    quality_score: Optional[float] = None
    confidence: Optional[float] = None
    retry_count: int = 0
    total_time_ms: int = 0
    tools_used: list = []
    sources: list = []
    trace: list = []
    conv_id: Optional[int] = None
    memory_ids: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class PromptPreviewRequest(BaseModel):
    message: str
    persona: str = "helpful"
    lang: str = "de"
    conv_id: Optional[int] = None
    force_fresh: Optional[bool] = None


class WebSearchDebugRequest(BaseModel):
    query: str = Field(min_length=1)
    lang: str = "de"
    max_results: int = Field(default=5, ge=1, le=20)
    mode: Optional[str] = None
    country: Optional[str] = None
    user_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Multi-stage pipeline helpers
# ---------------------------------------------------------------------------


@dataclass
class SafetyDecision:
    """Represents the outcome of the safety layer for a user prompt."""

    allowed: bool
    sanitized_text: str
    fallback_reply: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


class MultiStageChatPipeline:
    """Orchestrates the multi-layer chat pipeline for /api/v2/chat."""

    def __init__(
        self,
        *,
        llm_primary,
        llm_fallback,
        memory_fetcher: Optional[Callable[[str], Dict[str, Any]]] = None,
        web_enricher: Optional[WebEnricher] = None,
        input_safety: Optional[Callable[[str, Dict[str, Any]], SafetyDecision]] = None,
        output_safety: Optional[Callable[[str, str, Dict[str, Any]], str]] = None,
        history_loader: Optional[Callable[[Dict[str, Any]], List[Dict[str, str]]]] = None,
    ) -> None:
        self.llm_primary = llm_primary
        self.llm_fallback = llm_fallback
        self.memory_fetcher = memory_fetcher
        self.web_enricher = web_enricher
        self.input_safety = input_safety
        self.output_safety = output_safety
        self.history_loader = history_loader or (lambda _: [])

        # Quality reflector (Stage between LLM + post-processing)
        try:
            reflector_backend = None
            if llm_primary and hasattr(llm_primary, "available"):
                try:
                    if llm_primary.available():
                        reflector_backend = llm_primary
                except Exception:
                    reflector_backend = None
            if reflector_backend is None and llm_fallback:
                reflector_backend = llm_fallback
            self.reflector: Optional[ResponseReflector] = get_reflector(reflector_backend)
        except Exception:
            self.reflector = None

        self.explanation_enricher = None
        if get_enricher:
            try:
                self.explanation_enricher = get_enricher()
            except Exception:  # pragma: no cover
                self.explanation_enricher = None

        # Default persona prompts (can be extended per persona)
        self.persona_prompts: Dict[str, str] = {
            "helpful": (
                "Du bist KI_ana, eine ruhige, reflektierende Begleiterin. Antworte empathisch, "
                "fokussiert und transparent über deine Wissensquellen."
            ),
            "friendly": "Du bist KI_ana in einer warmen, freundlichen Rolle. Bleib respektvoll und klar.",
        }

        self.system_ethics_hint = (
            "Beachte die Ethik-Regeln von KI_ana: Markiere sensible Inhalte, ermutige zu verantwortlichem "
            "Handeln und lehne gefährliche Anweisungen ab."
        )

    # ---------------- Stage 1: Input handling ----------------
    def _prepare_input(self, question: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        history = []
        try:
            history = list(self.history_loader(user_context) or [])
        except Exception as exc:  # pragma: no cover - defensive only
            logger.warning("history_loader failed: %s", exc)
            history = []
        return {
            "history": history,
            "question": question.strip(),
            "user_context": user_context or {},
        }

    # ---------------- Stage 2: Safety (input) ----------------
    def _run_input_safety(
        self,
        bundle: Dict[str, Any],
    ) -> SafetyDecision:
        question = bundle["question"]
        user_context = bundle.get("user_context", {})
        if not self.input_safety:
            return SafetyDecision(allowed=True, sanitized_text=question)
        try:
            decision = self.input_safety(question, user_context)
            if isinstance(decision, SafetyDecision):
                return decision
        except Exception as exc:  # pragma: no cover - defensive only
            logger.warning("input_safety handler failed: %s", exc)
        return SafetyDecision(allowed=True, sanitized_text=question)

    # ---------------- Stage 3: Memory ----------------
    def _retrieve_memory(
        self,
        question: str,
        context: PipelineContext,
    ) -> Tuple[str, List[str]]:
        if not self.memory_fetcher:
            return "", []
        try:
            result = self.memory_fetcher(question) or {}
        except Exception as exc:  # pragma: no cover - defensive only
            logger.warning("memory fetcher failed: %s", exc)
            return "", []

        hits = result.get("hits") or []
        memory_ids = result.get("memory_ids") or []
        if hits:
            summary_lines = []
            for hit in hits[:3]:
                title = str(hit.get("title") or "Notiz")
                content = str(hit.get("content") or "")
                summary_lines.append(f"- {title}: {content[:220]}")
            context.trace.append({"step": "memory", "items": len(summary_lines)})
            context.tools_used.append({"tool": "memory", "ok": True})
            return "\n".join(summary_lines), list(memory_ids)

        context.tools_used.append({"tool": "memory", "ok": True, "result_summary": "0 hits"})
        return "", []

    # ---------------- Stage 4: Web enrichment ----------------
    def _retrieve_web(
        self,
        question: str,
        context: PipelineContext,
        user_context: Dict[str, Any],
        explanation_tracker: Optional[Any] = None,
        explanation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.web_enricher:
            context.trace.append({"step": "web", "used": False, "reason": "not_configured"})
            context.tools_used.append({"tool": "web", "ok": False, "reason": "not_configured"})
            return {"used": False, "reason": "not_configured"}

        needs_current_flag = bool(context.flags.get("needs_current"))
        force_fresh_flag = bool(context.flags.get("force_fresh"))
        combined_force_fresh = bool(user_context.get("force_fresh_content") or force_fresh_flag or needs_current_flag)
        try:
            web_context = self.web_enricher.build_web_context(
                user_message=question,
                lang=user_context.get("lang"),
                user_locale=user_context.get("user_locale"),
                force_fresh=combined_force_fresh,
                user_context=user_context,
            )
        except Exception as exc:  # pragma: no cover - defensive safety net
            logger.warning("web enricher failed: %s", exc)
            web_context = {"used": False, "reason": "error", "error": str(exc)}

        if isinstance(web_context, dict):
            web_context.setdefault("required", bool(needs_current_flag))

        used = bool(web_context.get("used"))
        snippet_count = len(web_context.get("snippets") or [])
        summary_payload = web_context.get("summary") or {
            "query": web_context.get("query") or question,
            "num_results": snippet_count,
            "sources": [],
        }
        summary_payload.setdefault("query", web_context.get("query") or question)
        summary_payload.setdefault("num_results", snippet_count)
        summary_payload.setdefault("sources", [])
        if not used:
            summary_payload.setdefault("reason", web_context.get("reason"))

        if needs_current_flag and not used:
            logger.warning(
                "CHAT_PIPELINE_WEB_REQUIRED_FAILED: reason=%s provider=%s query=%r",
                web_context.get("reason"),
                web_context.get("provider") or web_context.get("active_provider"),
                web_context.get("query") or question,
            )

        trace_payload = {
            "step": "web",
            "used": used,
            "reason": web_context.get("reason"),
            "snippets": snippet_count,
        }
        context.trace.append(trace_payload)

        if used:
            context.tools_used.append({
                "tool": "web",
                "ok": True,
                "snippets": snippet_count,
                "result_summary": summary_payload,
            })
            for snippet in web_context.get("snippets", [])[:5]:
                context.sources.append({
                    "title": snippet.get("title"),
                    "url": snippet.get("url"),
                })
        else:
            context.tools_used.append({
                "tool": "web",
                "ok": False,
                "reason": web_context.get("reason"),
                "result_summary": summary_payload,
            })

        if explanation_tracker and explanation_id:
            try:
                if isinstance(summary_payload, dict):
                    explanation_tracker.attach_web_summary(explanation_id, summary_payload)
                news_context = web_context.get("news_context")
                if isinstance(news_context, dict):
                    explanation_tracker.attach_news_context(explanation_id, news_context)
                if used:
                    for snippet in (web_context.get("snippets") or [])[:5]:
                        trust_value = snippet.get("trust_score")
                        try:
                            trust_float = float(trust_value) if trust_value is not None else 0.0
                        except Exception:
                            trust_float = 0.0
                        explanation_tracker.add_source(
                            explanation_id,
                            source_id=snippet.get("url") or snippet.get("title") or "web",
                            source_type="web",
                            content_snippet=snippet.get("summary") or snippet.get("snippet") or "",
                            trust_score=trust_float,
                            url=snippet.get("url"),
                        )
                    explanation_tracker.add_step(
                        explanation_id,
                        action="web_enrichment",
                        description=f"Web-Suche mit {summary_payload.get('query') or question}",
                        result=f"{snippet_count} Snippets" if snippet_count else "keine Ergebnisse",
                    )
            except Exception:
                logger.debug("explanation: attach web context failed", exc_info=True)

        context.metadata["web"] = web_context
        context.metadata.setdefault("results_summary", {})["web"] = summary_payload
        return web_context

    def _retrieve_addressbook_boost(
        self,
        question: str,
        context: PipelineContext,
        explanation_tracker: Optional[Any] = None,
        explanation_id: Optional[str] = None,
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        entry: Optional[AddressBookEntrySnapshot]
        try:
            entry = match_entry_for_prompt(question)
        except Exception as exc:  # pragma: no cover
            logger.debug("addressbook boost matching failed: %s", exc)
            entry = None

        if not entry:
            return "", None

        try:
            blocks = load_boost_blocks(entry, limit=5)
        except Exception as exc:
            logger.debug("addressbook boost block load failed: %s", exc)
            blocks = []

        context.trace.append({
            "step": "addressbook_boost",
            "entry_id": entry.id,
            "blocks": len(blocks),
        })

        context.metadata.setdefault("addressbook_boost", {})["entry"] = {
            "id": entry.id,
            "title": entry.title,
            "domain": entry.domain,
            "blocks": len(blocks),
        }

        if not blocks:
            context.tools_used.append({
                "tool": "addressbook_boost",
                "ok": False,
                "entry_id": entry.id,
                "reason": "no_blocks",
            })
            return "", {"entry": entry, "blocks": []}

        summary = summarize_blocks_for_prompt(entry, blocks)
        context.tools_used.append({
            "tool": "addressbook_boost",
            "ok": True,
            "entry_id": entry.id,
            "blocks": len(blocks),
        })
        if blocks:
            context.sources.append({
                "title": entry.title,
                "url": blocks[0].get("url"),
                "type": "addressbook_boost",
            })

        if explanation_tracker and explanation_id:
            try:
                explanation_tracker.add_step(
                    explanation_id,
                    action="addressbook_boost",
                    description=f"Adressbuch-Booster für {entry.title}",
                    result=f"{len(blocks)} Blöcke",
                )
                for block in blocks[:3]:
                    explanation_tracker.add_source(
                        explanation_id,
                        source_id=block.get("id") or block.get("url") or f"entry-{entry.id}",
                        source_type="addressbook_boost",
                        content_snippet=self._shorten(block.get("content") or block.get("summary") or "", 220),
                        trust_score=block.get("score") or 0.0,
                        url=block.get("url"),
                    )
            except Exception:
                logger.debug("explanation: addressbook boost attach failed", exc_info=True)

        return summary, {"entry": entry, "blocks": blocks}

    # ---------------- Stage 5: LLM backend ----------------
    def _shorten(self, text: str, limit: int = 320) -> str:
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 1].rstrip() + "…"

    def _format_web_context(self, web_context: Dict[str, Any]) -> str:
        if not web_context:
            return ""
        if not web_context.get("used"):
            if web_context.get("required"):
                reason = web_context.get("reason") or "unknown"
                query = web_context.get("query") or ""
                provider = web_context.get("provider") or web_context.get("active_provider") or "unknown"
                return "\n".join(
                    [
                        "WEB-NEWS-ABFRAGE (ERFORDERLICH): fehlgeschlagen",
                        f"Reason: {reason}",
                        f"Provider: {provider}",
                        f"Query: {query}",
                        "Hinweis: Sei transparent, dass keine aktuellen Web-Quellen geladen werden konnten.",
                    ]
                )
            return ""
        summary = web_context.get("summary") or {}
        timestamp_display = summary.get("timestamp_local_display") or summary.get("timestamp_utc_iso")
        if not timestamp_display:
            timestamp_display = web_context.get("generated_at") or datetime.utcnow().strftime("%Y-%m-%d")
        country_label = summary.get("country_label") or (summary.get("country_focus") or "Global")

        lines = [
            f"NEWS DIGEST – Stand: {timestamp_display}",
            f"Fokus: {country_label}",
        ]

        highlights = summary.get("highlights") or []
        if highlights:
            lines.append("Schlagzeilen:")
            for item in highlights[:5]:
                title = item.get("title") or "Quelle"
                domain = item.get("domain") or ""
                summary_text = item.get("summary") or ""
                shortened = self._shorten(summary_text, 320)
                if domain:
                    lines.append(f"- {title} ({domain}): {shortened}")
                else:
                    lines.append(f"- {title}: {shortened}")

        source_domains = summary.get("source_domains") or []
        if source_domains:
            lines.append("Quellen: " + ", ".join(source_domains[:6]))

        lines.append("Antwortformat:")
        lines.append("1. Einleitung mit Hinweis auf Stand und Region.")
        lines.append("2. 3-5 Bulletpoints mit wichtigsten Entwicklungen (maximal zwei Sätze je Punkt).")
        lines.append("3. Abschluss: Hinweis auf dynamische Lage und Quellen/Datum nennen.")

        return "\n".join(lines)

    def _build_system_prompt(
        self,
        persona: str,
        memory_context: str,
        web_context: str,
        style_directive: Optional[str] = None,
        addressbook_context: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        context_payload = user_context or {}
        pipeline_flags = dict(context_payload.get("pipeline_flags") or {})
        intent_payload = context_payload.get("intent_result") if isinstance(context_payload.get("intent_result"), dict) else None

        tools_available: List[str] = []
        if memory_context:
            tools_available.append("memory")
        if addressbook_context:
            tools_available.append("addressbook_boost")
        if web_context:
            tools_available.append("web_search")
        if pipeline_flags.get("tool_preference") == "submind_orchestration":
            tools_available.append("submind")
        if pipeline_flags.get("internal_context"):
            tools_available.append("monitoring")

        extra_blocks: List[str] = []
        primary_intent = (intent_payload or {}).get("primary_intent")
        if pipeline_flags.get("needs_current") or primary_intent == "current_events":
            extra_blocks.append(CURRENT_EVENTS_SAFETY_PROMPT)
        if pipeline_flags.get("safety_mode") == "strict" or primary_intent == "sensitive_high_risk":
            extra_blocks.append(SENSITIVE_SAFETY_PROMPT)

        prompt_context = PromptContext(
            persona_prompt=self.persona_prompts.get(persona, self.persona_prompts["helpful"]),
            ethics_hint=self.system_ethics_hint,
            time_info=self._build_time_context(context_payload),
            intent_result=intent_payload,
            pipeline_flags=pipeline_flags,
            memory_context=memory_context,
            web_context=web_context,
            addressbook_context=addressbook_context,
            style_directive=style_directive,
            tools_available=tools_available,
            extra_blocks=extra_blocks,
            submind_context=context_payload.get("submind_context"),
        )
        return build_system_prompt(prompt_context)

    def _build_time_context(self, user_context: Dict[str, Any]) -> str:
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        lines = [f"Aktuelle interne Zeit: {now_str}"]
        try:
            user_locale = user_context.get("user_locale") if isinstance(user_context, dict) else None
            if isinstance(user_locale, dict):
                locale_value = user_locale.get("value") or user_locale.get("country_code")
                if locale_value:
                    lines.append(f"Nutzer-Lokalisierung: {locale_value}")
            city = user_context.get("city") if isinstance(user_context, dict) else None
            if city:
                lines.append(f"Nutzer-Stadt: {city}")
        except Exception:
            pass
        return "\n".join(lines)

    def _build_user_prompt(
        self,
        sanitized_text: str,
        history: List[Dict[str, str]],
    ) -> str:
        if not history:
            return sanitized_text
        transcript = []
        for turn in history[-6:]:
            role = str(turn.get("role") or "user").upper()
            text = str(turn.get("text") or "")
            transcript.append(f"{role}: {text}")
        transcript.append(f"USER: {sanitized_text}")
        return "\n".join(transcript)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        backend = None
        if self.llm_primary and hasattr(self.llm_primary, "available"):
            try:
                if self.llm_primary.available():
                    backend = self.llm_primary
            except Exception as exc:
                logger.warning("llm_primary availability check failed: %s", exc)

        if backend is None and self.llm_fallback:
            backend = self.llm_fallback

        if not backend:
            raise RuntimeError("No LLM backend configured")

        try:
            return backend.chat_once(user=user_prompt, system=system_prompt) or ""
        except Exception as exc:
            logger.warning("LLM backend failed: %s", exc)
            if backend is not self.llm_fallback and self.llm_fallback:
                try:
                    return self.llm_fallback.chat_once(user=user_prompt, system=system_prompt) or ""
                except Exception:
                    pass
            return ""

    # ---------------- Stage 6: Post-processing ----------------
    def _run_output_safety(
        self,
        original_prompt: str,
        llm_reply: str,
        user_context: Dict[str, Any],
    ) -> str:
        if not self.output_safety:
            return llm_reply
        try:
            safe_text = self.output_safety(original_prompt, llm_reply, user_context)
            if safe_text:
                return safe_text
        except Exception as exc:  # pragma: no cover
            logger.warning("output_safety handler failed: %s", exc)
        return llm_reply

    def _should_store_memory(self, question: str, user_context: Dict[str, Any]) -> bool:
        user_id = user_context.get("user_id") if isinstance(user_context, dict) else None
        role = str(user_context.get("role") or "").lower() if isinstance(user_context, dict) else ""
        if not user_id or role not in {"creator", "admin", "papa"}:
            return False
        q = (question or "").lower()
        triggers = [
            "merk dir",
            "merke dir",
            "bitte merken",
            "speichere",
            "notiere",
            "remember this",
            "save this",
            "store this",
        ]
        return any(t in q for t in triggers)

    def _prepare_style_bundle(
        self,
        *,
        sanitized_text: str,
        user_context: Dict[str, Any],
        persona: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            from netapi.modules.style.engine import get_style_engine
            from netapi.modules.style.topic import get_topic_detector
        except Exception as exc:
            logger.debug("StyleEngine not available: %s", exc)
            return None

        style_engine = None
        topic_result = None
        try:
            style_engine = get_style_engine()
            topic_result = get_topic_detector().detect(sanitized_text)
        except Exception as exc:
            logger.warning("Failed to initialise style components: %s", exc)
            return None

        personality_traits = None
        mood_hint = None
        try:
            from dynamic_personality import get_dynamic_personality  # type: ignore

            personality = get_dynamic_personality()
            mood_hint = personality.detect_user_mood(sanitized_text)
            personality_traits = personality.get_current_traits({"user_mood": mood_hint})
        except Exception:
            personality_traits = None

        affect_engine = None
        emotion_label = "neutral"
        emotion_intensity = 0.5
        resonance = None
        try:
            from netapi.modules.emotion.affect_engine import get_affect_engine  # type: ignore

            affect_engine = get_affect_engine()
            emotion_label, raw_intensity = affect_engine.detect_emotion(sanitized_text)
            emotion_intensity = max(0.0, min(1.0, float(raw_intensity)))
            resonance = affect_engine.get_resonance_parameters(emotion_label, emotion_intensity)
        except Exception as exc:
            logger.debug("AffectEngine unavailable: %s", exc)
            affect_engine = None
            emotion_label = "neutral"
            emotion_intensity = 0.5
            resonance = None

        timeflow_state = None
        try:
            from netapi.modules.timeflow.state import get_timeflow  # type: ignore

            timeflow_state = get_timeflow().snapshot()
        except Exception as exc:
            logger.debug("TimeFlow snapshot failed: %s", exc)
            timeflow_state = None

        try:
            directive, metadata = style_engine.generate_directive(
                prompt=sanitized_text,
                personality=personality_traits,
                emotion_label=emotion_label,
                emotion_intensity=emotion_intensity,
                resonance=resonance,
                timeflow=timeflow_state,
                topic=topic_result.topic,
                topic_confidence=topic_result.confidence,
                topic_evidence=list(topic_result.evidence),
            )
        except Exception as exc:
            logger.warning("StyleEngine.generate_directive failed: %s", exc)
            return None

        style_meta = dict(metadata or {})
        style_meta["mood_hint"] = mood_hint
        if timeflow_state is not None:
            style_meta["timeflow_snapshot"] = timeflow_state

        return {
            "style_prompt": directive,
            "metadata": style_meta,
            "adjuster": affect_engine,
        }

    # Public API -------------------------------------------------------------
    def generate(
        self,
        *,
        question: str,
        user_context: Optional[Dict[str, Any]] = None,
        persona: str = "helpful",
        lang: str = "de",
    ) -> PipelineResponse:
        user_context = user_context or {}
        start_time = time.time()
        pipe_context = PipelineContext(question=question)
        initial_flags = {}
        try:
            if isinstance(user_context, dict):
                maybe_flags = user_context.get("pipeline_flags")
                if isinstance(maybe_flags, dict):
                    initial_flags = dict(maybe_flags)
        except Exception:
            initial_flags = {}
        if initial_flags:
            pipe_context.flags.update(initial_flags)
            pipe_context.metadata.setdefault("pipeline_flags", {}).update(initial_flags)
        intent_payload = None
        try:
            if isinstance(user_context, dict):
                maybe_intent = user_context.get("intent_result")
                if isinstance(maybe_intent, dict):
                    intent_payload = maybe_intent
        except Exception:
            intent_payload = None
        if intent_payload:
            pipe_context.metadata.setdefault("intent_result", intent_payload)

        # Stage 1 – Input handling
        bundle = self._prepare_input(question, user_context)
        pipe_context.trace.append({"step": "input", "history_len": len(bundle["history"])})

        # Stage 2 – Safety (input)
        decision = self._run_input_safety(bundle)
        if not decision.allowed:
            reply = decision.fallback_reply or (
                "⚠️ Diese Anfrage kann ich so nicht besprechen. Lass uns gemeinsam überlegen, "
                "wie wir verantwortungsvoll weiterkommen."
            )
            total = int((time.time() - start_time) * 1000)
            pipe_context.trace.append({"step": "input_safety_block", "meta": decision.meta})
            return PipelineResponse(
                ok=True,
                reply=reply,
                evaluation=None,
                context=pipe_context,
                retry_count=0,
                total_time_ms=total,
            )

        sanitized_text = decision.sanitized_text

        explanation_tracker = self.explanation_enricher
        explanation_id: Optional[str] = None
        if explanation_tracker is not None:
            try:
                explanation_id = explanation_tracker.start_explanation(sanitized_text)
                pipe_context.metadata.setdefault("explanation_id", explanation_id)
            except Exception:  # pragma: no cover
                explanation_id = None

        # Stage 3 – Memory
        memory_context, memory_ids = self._retrieve_memory(sanitized_text, pipe_context)
        if memory_ids:
            pipe_context.memory_ids.extend(memory_ids)

        # Stage 4 – Addressbook booster
        addressbook_context, _booster_details = self._retrieve_addressbook_boost(
            sanitized_text,
            pipe_context,
            explanation_tracker=explanation_tracker,
            explanation_id=explanation_id,
        )

        # Stage 5 – Web enrichment (skippable)
        skip_web_due_to_boost = bool(addressbook_context) and not user_context.get("force_fresh_content")
        web_metadata: Dict[str, Any] = {}
        if skip_web_due_to_boost:
            summary_payload = {
                "query": sanitized_text,
                "used": False,
                "reason": "skipped_addressbook_boost",
            }
            pipe_context.trace.append({
                "step": "web",
                "used": False,
                "reason": "skipped_addressbook_boost",
            })
            pipe_context.tools_used.append({
                "tool": "web",
                "ok": False,
                "reason": "skipped_addressbook_boost",
                "result_summary": summary_payload,
            })
            pipe_context.metadata.setdefault("results_summary", {})["web"] = summary_payload
            pipe_context.metadata["web"] = summary_payload
            web_context = ""
        else:
            web_metadata = self._retrieve_web(
                sanitized_text,
                pipe_context,
                user_context,
                explanation_tracker=explanation_tracker,
                explanation_id=explanation_id,
            )
            web_context = self._format_web_context(web_metadata)

        style_bundle = self._prepare_style_bundle(
            sanitized_text=sanitized_text,
            user_context=user_context,
            persona=persona,
        )

        style_prompt_extra = ""
        if style_bundle:
            style_prompt_extra = style_bundle.get("style_prompt") or ""
            style_meta = style_bundle.get("metadata") or {}
            pipe_context.metadata["style_engine"] = style_meta
            pipe_context.trace.append({
                "step": "style_engine",
                "topic": style_meta.get("topic"),
                "confidence": style_meta.get("topic_confidence"),
            })

        # Stage 5 – LLM backend
        system_prompt = self._build_system_prompt(
            persona,
            memory_context,
            web_context,
            style_directive=style_prompt_extra or None,
            addressbook_context=addressbook_context or None,
            user_context=user_context,
        )
        pipe_context.metadata["system_prompt_preview"] = system_prompt
        user_prompt = self._build_user_prompt(sanitized_text, bundle.get("history", []))
        llm_reply = self._call_llm(system_prompt, user_prompt)

        if not llm_reply:
            llm_reply = (
                "Ich konnte gerade keine vollständige Antwort generieren. Lass uns den Punkt "
                "gemeinsam weiter ausleuchten oder die Frage anders formulieren."
            )

        if style_bundle and style_bundle.get("adjuster"):
            try:
                style_meta = style_bundle.get("metadata") or {}
                emotion_label = style_meta.get("emotion_label") or "neutral"
                emotion_intensity = float(style_meta.get("emotion_intensity") or 0.0)
                llm_reply = style_bundle["adjuster"].adjust_response(  # type: ignore[attr-defined]
                    llm_reply,
                    emotion_label,
                    emotion_intensity,
                )
            except Exception as exc:
                logger.debug("Emotion adjustment failed: %s", exc)

        evaluation = None
        if self.reflector:
            try:
                evaluation = self.reflector.evaluate(
                    question=sanitized_text,
                    answer=llm_reply,
                    context=pipe_context.to_dict(),
                )
                pipe_context.trace.append(
                    {
                        "step": "reflection",
                        "score": evaluation.overall_score,
                        "needs_retry": evaluation.needs_retry,
                    }
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("quality reflector failed: %s", exc)
                evaluation = None

        # Stage 6 – Output safety & logging
        safe_reply = self._run_output_safety(sanitized_text, llm_reply, user_context)

        # Stage 7 – Memory write-back (explicit user intent only)
        if _memory_store is not None and self._should_store_memory(sanitized_text, user_context):
            try:
                title = (sanitized_text.strip() or "Notiz")
                if len(title) > 120:
                    title = title[:117].rstrip() + "…"
                content = f"User: {sanitized_text.strip()}\n\nAssistant: {safe_reply.strip()}"
                mid = _memory_store.add_block(
                    title=title,
                    content=content,
                    tags=["chat", "user_requested"],
                    url=None,
                )
                if mid:
                    try:
                        pipe_context.memory_ids.append(str(mid))
                    except Exception:
                        pass
                pipe_context.metadata["memory_writeback"] = {"ok": True, "id": mid}
            except Exception as exc:  # pragma: no cover
                pipe_context.metadata["memory_writeback"] = {"ok": False, "error": str(exc)}

        if explanation_tracker is not None and explanation_id:
            try:
                explanation_payload = explanation_tracker.finalize(explanation_id, safe_reply)
                if explanation_payload:
                    pipe_context.metadata.setdefault("explanation", explanation_payload)
            except Exception:
                logger.debug("explanation: finalize failed", exc_info=True)

        total_time = int((time.time() - start_time) * 1000)
        return PipelineResponse(
            ok=True,
            reply=safe_reply,
            evaluation=evaluation,
            context=pipe_context,
            retry_count=0,
            total_time_ms=total_time,
        )


# Global pipeline instance (created on first use)
_pipeline: Optional[MultiStageChatPipeline] = None


def get_pipeline() -> MultiStageChatPipeline:
    """Get or create global multi-stage chat pipeline instance."""
    global _pipeline

    if _pipeline is None:
        # --- LLM backends -------------------------------------------------
        primary_backend = None
        try:
            from netapi.core import llm_local  # type: ignore
            primary_backend = llm_local
        except Exception:
            primary_backend = None

        fallback_backend = None
        try:
            from netapi.core import llm_mock  # type: ignore
            fallback_backend = llm_mock
        except Exception:
            fallback_backend = None

        if primary_backend is None and fallback_backend is None:
            raise RuntimeError("No LLM backend modules could be imported.")

        # --- Memory fetcher ----------------------------------------------
        def memory_fetcher(question: str) -> Dict[str, Any]:
            try:
                hits, ids = tool_memory_search(question, top_k=5)
            except Exception as exc:  # pragma: no cover
                logger.warning("memory search failed: %s", exc)
                return {"hits": [], "memory_ids": []}
            return {"hits": hits, "memory_ids": ids}

        # --- Web enrichment ----------------------------------------------
        try:
            web_enricher = WebEnricher()
        except Exception as exc:  # pragma: no cover - defensive only
            logger.warning("failed to initialise WebEnricher: %s", exc)
            web_enricher = None

        # --- Input safety wrapper ---------------------------------------
        input_safety_handler: Optional[Callable[[str, Dict[str, Any]], SafetyDecision]] = None
        try:
            from netapi.modules.safety import guard as safety_guard  # type: ignore

            if hasattr(safety_guard, "assess_prompt"):

                def _input_guard(prompt: str, user_ctx: Dict[str, Any]) -> SafetyDecision:
                    assessment = safety_guard.assess_prompt(prompt, user_ctx)
                    if not assessment:
                        return SafetyDecision(True, prompt)
                    blocked = bool(assessment.get("blocked"))
                    sanitized = assessment.get("sanitized") or prompt
                    fallback = assessment.get("fallback_reply")
                    return SafetyDecision(
                        allowed=not blocked,
                        sanitized_text=str(sanitized),
                        fallback_reply=str(fallback) if fallback else None,
                        meta=assessment,
                    )

                input_safety_handler = _input_guard
        except Exception:
            input_safety_handler = None

        # --- Output safety wrapper --------------------------------------
        output_safety_handler: Optional[Callable[[str, str, Dict[str, Any]], str]] = None
        try:
            from netapi.modules.safety import output_filter  # type: ignore

            if hasattr(output_filter, "sanitize_reply"):

                def _output_guard(prompt: str, reply: str, user_ctx: Dict[str, Any]) -> str:
                    sanitized = output_filter.sanitize_reply(prompt=prompt, reply=reply, user_context=user_ctx)
                    return str(sanitized) if sanitized else reply

                output_safety_handler = _output_guard
        except Exception:
            output_safety_handler = None

        # --- Conversation history loader --------------------------------
        history_loader: Optional[Callable[[Dict[str, Any]], List[Dict[str, str]]]] = None
        try:
            from netapi.modules.chat import history as chat_history  # type: ignore

            if hasattr(chat_history, "load_recent_turns"):

                def _history_loader(user_ctx: Dict[str, Any]) -> List[Dict[str, str]]:
                    conv_id = user_ctx.get("conv_id")
                    user_id = user_ctx.get("user_id")
                    if conv_id is None or user_id is None:
                        return []
                    turns = chat_history.load_recent_turns(user_id=user_id, conversation_id=conv_id, limit=12)
                    return [
                        {"role": t.get("role", "user"), "text": t.get("text", "")}
                        for t in (turns or [])
                    ]

                history_loader = _history_loader
        except Exception:
            history_loader = None

        _pipeline = MultiStageChatPipeline(
            llm_primary=primary_backend,
            llm_fallback=fallback_backend,
            memory_fetcher=memory_fetcher,
            web_enricher=web_enricher,
            input_safety=input_safety_handler,
            output_safety=output_safety_handler,
            history_loader=history_loader,
        )

    return _pipeline


async def run_chat_pipeline_from_message(
    message: str,
    *,
    conv_id: Optional[int],
    request: Request,
    db,
    current: Optional[Dict[str, Any]],
    lang: Optional[str] = None,
    persona: Optional[str] = None,
    force_fresh: Optional[bool] = None,
    save_messages: bool = True,
) -> ChatResponse:
    """Execute the shared chat pipeline for both v1 and v2 callers."""

    if not message or not message.strip():
        raise HTTPException(HTTP_400_BAD_REQUEST, "Message cannot be empty")

    def _current_value(key: str) -> Any:
        if isinstance(current, dict):
            return current.get(key)
        if current is None:
            return None
        return getattr(current, key, None)

    user_id = _current_value("id")
    logger.info(
        "CHAT_PIPELINE: message=%r user_id=%s",
        (message or "")[:200],
        user_id,
    )

    abuse_guard = None
    try:
        from netapi.modules.security import get_abuse_guard

        abuse_guard = get_abuse_guard()
    except Exception as exc:
        logger.warning("Abuse Guard unavailable: %s", exc)
        abuse_guard = None

    if abuse_guard is not None:
        client_ip = request.client.host if request.client else None
        try:
            check_result = await abuse_guard.check_prompt(message, user_id, client_ip)
            if not check_result["allowed"]:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "Content policy violation",
                        "reason": check_result.get("reason"),
                        "severity": check_result.get("severity"),
                    },
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Abuse Guard check failed: %s", exc)

    try:
        pipeline = get_pipeline()
    except Exception as exc:
        raise HTTPException(
            HTTP_500_INTERNAL_SERVER_ERROR,
            f"Pipeline initialization failed: {exc}",
        ) from exc

    persona_value = persona or "helpful"
    lang_value = lang or "de"

    user_context: Dict[str, Any] = {}
    locale_payload: Dict[str, Any] = {}

    if current:
        user_context["user_id"] = user_id
        user_context["role"] = _current_value("role")
        user_context["is_papa"] = bool(_current_value("is_papa") or False)
        locale_hint = build_user_locale_from_user(current)
        if locale_hint:
            locale_payload["value"] = locale_hint
        country_code = _current_value("country_code")
        if country_code:
            user_context["country_code"] = country_code
            locale_payload["country_code"] = str(country_code).upper()
        city = _current_value("city")
        if city:
            user_context["city"] = city
        postal_code = _current_value("postal_code")
        if postal_code:
            user_context["postal_code"] = postal_code
        if locale_payload:
            user_context["user_locale"] = locale_payload

    if conv_id is not None:
        user_context["conv_id"] = conv_id
    if lang_value:
        user_context["lang"] = lang_value
    if persona_value:
        user_context["persona"] = persona_value

    try:
        intent_result = detect_intents(message)
    except Exception:
        intent_result = IntentResult()

    pipeline_flags: Dict[str, Any] = apply_intent_to_pipeline(intent_result, user_context.get("pipeline_flags"))

    tags = list(user_context.get("intent_tags") or [])
    for tag in [intent_result.primary_intent, *intent_result.secondary_intents]:
        if tag and tag not in tags:
            tags.append(tag)
    user_context["intent_tags"] = tags
    user_context["intent_result"] = intent_result.to_dict()

    news_intent = intent_result.primary_intent == "current_events" or "current_events" in intent_result.secondary_intents
    if news_intent:
        pipeline_flags.setdefault("is_news", True)
        if user_context.get("country_code"):
            user_context.setdefault("news_country_hint", user_context["country_code"])

    try:
        needs_current, current_reason = needs_current_info(message)
    except Exception:
        needs_current, current_reason = False, None

    if news_intent and not needs_current:
        needs_current = True
        current_reason = current_reason or "News-Intent erkannt"

    # --- PR2: Ask for missing source preferences (human-style) ---------
    # Only for authenticated users (we need a stable user_id to store prefs).
    try:
        if user_id is not None and (news_intent or needs_current):
            country = str(user_context.get("country_code") or "AT").strip().upper()[:2] or "AT"
            lang_norm = str(user_context.get("lang") or "de").strip().lower() or "de"
            conv_for_check = user_context.get("conv_id")

            from netapi.core import addressbook

            existing_bid = addressbook.get_source_prefs(
                user_id=int(user_id),
                country=country,
                lang=lang_norm,
                intent="news",
            )
            missing_prefs = not bool(existing_bid)

            asked_once = _asked_sources_once(int(user_id), int(conv_for_check)) if conv_for_check is not None else False

            if missing_prefs and not asked_once:
                question = (
                    f"Welche 1-3 Seiten bevorzugst du fuer Nachrichten in {country} ({lang_norm.upper()})? "
                    "ORF, Standard, Presse, APA oder andere?"
                )
                return ChatResponse(
                    ok=True,
                    reply=question,
                    meta={
                        "needs_source_prefs": True,
                        "source_prefs_country": country,
                        "source_prefs_lang": lang_norm,
                        "source_prefs_intent": "news",
                    },
                )

            if missing_prefs and asked_once and _looks_like_source_prefs_answer(message):
                from netapi.modules.chat.source_prefs_parser import parse_source_prefs_user_text
                from netapi import memory_store

                parsed = parse_source_prefs_user_text(message)
                if (parsed.preferred_add or parsed.blocked_add) or parsed.notes:
                    preferred = list(parsed.preferred_add or [])
                    blocked = list(parsed.blocked_add or [])

                    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
                    meta = {
                        "type": "user_source_prefs",
                        "user_id": int(user_id),
                        "country": country,
                        "lang": lang_norm,
                        "intent": "news",
                        "preferred_sources": preferred,
                        "blocked_sources": blocked,
                        "trust_overrides": {},
                        "notes": parsed.notes,
                        "created_at": now,
                        "updated_at": now,
                    }
                    title = f"Source Prefs: user={int(user_id)} {country} {lang_norm} news"
                    content = json.dumps(meta, ensure_ascii=False, indent=2)
                    tags = [
                        "user_source_prefs",
                        "prefs:sources",
                        f"user:{int(user_id)}",
                        f"country:{country}",
                        f"lang:{lang_norm}",
                        "intent:news",
                    ]
                    tags.extend([f"pref:{d}" for d in preferred])
                    tags.extend([f"block:{d}" for d in blocked])

                    bid = memory_store.add_block(title=title, content=content, tags=tags, meta=meta)
                    addressbook.index_source_prefs(
                        block_id=bid,
                        user_id=int(user_id),
                        country=country,
                        lang=lang_norm,
                        intent="news",
                        preferred=preferred,
                        blocked=blocked,
                        trust_overrides={},
                        updated_at=now,
                    )

                    pref_str = ", ".join(preferred) if preferred else "(keine)"
                    block_str = ", ".join(blocked) if blocked else "(keine)"
                    ack = f"Alles klar. Bevorzugt: {pref_str}. Blockiert: {block_str}."
                    return ChatResponse(ok=True, reply=ack, meta={"stored_source_prefs": True, "block_id": bid})
    except Exception as exc:
        logger.warning("PR2 source prefs flow failed: %s", exc)

    if needs_current:
        if "current_info" not in user_context["intent_tags"]:
            user_context["intent_tags"].append("current_info")
        pipeline_flags["needs_current"] = True
        if current_reason:
            user_context.setdefault("current_info_reason", current_reason)
            pipeline_flags.setdefault("current_reason", current_reason)

    if pipeline_flags.get("needs_current"):
        user_context["force_fresh_content"] = True

    if force_fresh is not None:
        user_context["force_fresh_content"] = bool(force_fresh)
        if force_fresh:
            pipeline_flags["force_fresh"] = True

    if user_context.get("force_fresh_content"):
        pipeline_flags["force_fresh"] = True
    else:
        user_context.setdefault("force_fresh_content", False)

    if pipeline_flags:
        user_context["pipeline_flags"] = pipeline_flags

    logger.info(
        "CHAT_PIPELINE_INTENT: primary=%s secondary=%s flags=%s",
        intent_result.primary_intent,
        intent_result.secondary_intents,
        {k: pipeline_flags.get(k) for k in sorted(pipeline_flags.keys())},
    )

    try:
        pipeline_response = pipeline.generate(
            question=message,
            user_context=user_context,
            persona=persona_value,
            lang=lang_value,
        )
    except Exception as exc:
        raise HTTPException(
            HTTP_500_INTERNAL_SERVER_ERROR,
            f"Response generation failed: {exc}",
        ) from exc

    meta_payload: Dict[str, Any] = {}
    if pipeline_response.context and pipeline_response.context.metadata:
        meta_payload.update(pipeline_response.context.metadata)

    style_meta: Dict[str, Any] = {}
    try:
        raw_style_meta = meta_payload.get("style_engine")
        if isinstance(raw_style_meta, dict):
            style_meta = raw_style_meta
    except Exception:
        style_meta = {}

    if style_meta:
        if style_meta.get("topic") and "topic" not in meta_payload:
            meta_payload["topic"] = style_meta.get("topic")
        if style_meta.get("topic_confidence") is not None:
            meta_payload.setdefault("topic_confidence", style_meta.get("topic_confidence"))
        try:
            from netapi.modules.style.engine import get_style_engine, StyleInteractionSummary  # type: ignore

            style_engine = get_style_engine()
            quality_score = None
            feedback_score = 0.0
            if pipeline_response.evaluation and pipeline_response.evaluation.overall_score is not None:
                quality_score = float(pipeline_response.evaluation.overall_score)
                feedback_score = max(-1.0, min(1.0, (quality_score - 0.5) * 2.0))
            traits_used = {
                str(k): float(v)
                for k, v in (style_meta.get("traits") or {}).items()
            }
            style_engine.update_style_state(
                StyleInteractionSummary(
                    feedback_score=feedback_score,
                    topic=style_meta.get("topic"),
                    style_traits_used=traits_used,
                    is_strong_signal=abs(feedback_score) > 0.6,
                    quality_score=quality_score,
                    response_length=len(pipeline_response.reply or ""),
                    emotion_label=style_meta.get("emotion_label"),
                    emotion_intensity=style_meta.get("emotion_intensity"),
                )
            )
        except Exception as exc:
            logger.warning("StyleEngine update failed: %s", exc)

    ethics_result: Dict[str, Any] = {}
    try:
        persona_payload: Dict[str, Any] = {"persona": persona_value}
        if user_id is not None:
            persona_payload["user_id"] = user_id
        ethics_result = ethics_eval.analyze_interaction(
            message,
            pipeline_response.reply,
            persona_payload,
        )
    except Exception as exc:
        logger.warning("ethics_eval failed: %s", exc)
        ethics_result = {}

    category = ethics_result.get("category") if ethics_result else None
    risk_level = ethics_result.get("risk_level") if ethics_result else None
    note = ethics_result.get("note") if ethics_result else None
    tags_raw = ethics_result.get("tags") if ethics_result else None

    if isinstance(tags_raw, list):
        ethics_tags: List[Any] = tags_raw
    elif tags_raw is None:
        ethics_tags = []
    else:
        ethics_tags = [tags_raw]

    meta_payload["ethics_category"] = category
    meta_payload["ethics_risk_level"] = risk_level
    meta_payload["ethics_note"] = note
    meta_payload["ethics_tags"] = ethics_tags

    meta_payload.setdefault("intent_tags", user_context.get("intent_tags"))
    meta_payload.setdefault("force_fresh_content", user_context.get("force_fresh_content"))
    if news_intent:
        meta_payload.setdefault("detected_news_intent", True)
    if pipeline_flags:
        meta_payload.setdefault("pipeline_flags", pipeline_flags)
    intent_payload = user_context.get("intent_result")
    if isinstance(intent_payload, dict):
        meta_payload.setdefault("intent_result", intent_payload)
        meta_payload.setdefault("primary_intent", intent_payload.get("primary_intent"))
    if needs_current:
        meta_payload.setdefault("needs_current", True)
        if current_reason:
            meta_payload.setdefault("current_info_reason", current_reason)

    saved_user_msg = None
    saved_ai_msg = None
    resolved_conv_id = conv_id
    if save_messages and current and user_id:
        try:
            from .router import _ensure_conversation, _save_msg, _serialize_message  # type: ignore

            conv = _ensure_conversation(db, int(user_id), conv_id)
            resolved_conv_id = conv.id
            saved_user_msg = _save_msg(db, conv.id, "user", message)
            saved_ai_msg = _save_msg(db, conv.id, "ai", pipeline_response.reply or "")
            saved_messages_payload: Dict[str, Any] = {}
            if saved_user_msg:
                saved_messages_payload["user"] = _serialize_message(saved_user_msg)
            if saved_ai_msg:
                saved_messages_payload["ai"] = _serialize_message(saved_ai_msg)
            if saved_messages_payload:
                meta_payload.setdefault("saved_messages", {}).update(saved_messages_payload)
        except Exception as exc:
            logger.warning("Conversation save failed: %s", exc)

    if current and user_id and ethics_result:
        try:
            risk_level_str = str(ethics_result.get("risk_level") or "low")
        except Exception:
            risk_level_str = "low"
        if risk_level_str in {"medium", "high"}:
            logger.warning(
                "ETHICS_HINT user=%s risk=%s category=%s",
                user_id,
                risk_level_str,
                ethics_result.get("category"),
            )
            try:
                print(
                    "ETHICS_HINT",
                    "user=", user_id,
                    "risk=", risk_level_str,
                    "category=", ethics_result.get("category"),
                )
            except Exception:
                pass
            try:
                record_ethics_hint_event(
                    db,
                    user_id=user_id,
                    category=str(ethics_result.get("category") or "allgemein"),
                    risk_level=risk_level_str,
                    note=str(ethics_result.get("note") or ""),
                    conversation_id=resolved_conv_id or conv_id,
                )
            except Exception as exc:
                logger.warning("Failed to log ethics hint event: %s", exc)
        if risk_level_str == "high" and write_audit:
            try:
                write_audit(
                    "ethics_hint",
                    actor_id=int(user_id or 0),
                    target_type="conversation",
                    target_id=int(resolved_conv_id or conv_id or 0),
                    meta={
                        "category": ethics_result.get("category"),
                        "note": ethics_result.get("note"),
                        "tags": ethics_result.get("tags"),
                    },
                )
            except Exception as exc:
                logger.warning("Failed to write ethics audit: %s", exc)

    return ChatResponse(
        ok=pipeline_response.ok,
        reply=pipeline_response.reply,
        quality_score=pipeline_response.evaluation.overall_score if pipeline_response.evaluation else None,
        confidence=pipeline_response.evaluation.confidence if pipeline_response.evaluation else None,
        retry_count=pipeline_response.retry_count,
        total_time_ms=pipeline_response.total_time_ms,
        tools_used=pipeline_response.context.tools_used if pipeline_response.context else [],
        sources=pipeline_response.context.sources if pipeline_response.context else [],
        trace=pipeline_response.context.trace if pipeline_response.context else [],
        memory_ids=pipeline_response.context.memory_ids if pipeline_response.context else [],
        conv_id=resolved_conv_id,
        meta=meta_payload,
    )


class _PromptPreviewLLM:
    """Minimal backend that returns empty replies for prompt preview requests."""

    def available(self) -> bool:  # pragma: no cover - trivial
        return True

    def chat_once(self, user: str, system: str) -> str:  # pragma: no cover - trivial
        return ""


def _prompt_preview_allowed() -> bool:
    env_value = (os.getenv("KIANA_ENV") or os.getenv("ENV") or "dev").lower()
    if env_value in {"dev", "development", "test", "testing"}:
        return True
    override = (os.getenv("PROMPT_DEBUG_PREVIEW") or "").strip().lower()
    return override in {"1", "true", "yes", "on"}


@router.post("", response_model=ChatResponse)
async def chat_v2(
    body: ChatRequest,
    request: Request,
    current = Depends(get_current_user_opt),
    db = Depends(get_db)
):
    """Clean chat endpoint that delegates to the shared pipeline helper."""

    try:
        return await run_chat_pipeline_from_message(
            message=body.message,
            conv_id=body.conv_id,
            request=request,
            db=db,
            current=current,
            lang=body.lang,
            persona=body.persona,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            HTTP_500_INTERNAL_SERVER_ERROR,
            f"Response generation failed: {exc}",
        ) from exc


@router.post("/debug/prompt_preview")
async def prompt_preview(
    body: PromptPreviewRequest,
    request: Request,
    current = Depends(get_current_user_opt),
    db = Depends(get_db),
):
    if not _prompt_preview_allowed():
        raise HTTPException(404, "Prompt preview is not available in this environment")
    if current and str(current.get("role") or "").lower() not in {"creator", "admin"}:
        raise HTTPException(403, "Prompt preview requires creator/admin role")

    try:
        pipeline = get_pipeline()
    except Exception as exc:
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, f"Pipeline initialization failed: {exc}") from exc

    preview_backend = _PromptPreviewLLM()
    original_primary = pipeline.llm_primary
    original_fallback = pipeline.llm_fallback
    try:
        pipeline.llm_primary = preview_backend
        pipeline.llm_fallback = preview_backend
        response = await run_chat_pipeline_from_message(
            message=body.message,
            conv_id=body.conv_id,
            request=request,
            db=db,
            current=current,
            lang=body.lang,
            persona=body.persona,
            force_fresh=body.force_fresh,
            save_messages=False,
        )
    finally:
        pipeline.llm_primary = original_primary
        pipeline.llm_fallback = original_fallback

    meta = response.meta or {}
    web_meta = meta.get("web") if isinstance(meta, dict) else None
    web_included = {
        "used": False,
        "snippets": 0,
        "provider": None,
        "reason": None,
    }
    if isinstance(web_meta, dict):
        snippets = web_meta.get("snippets") or []
        web_included = {
            "used": bool(web_meta.get("used")),
            "snippets": len(snippets) if isinstance(snippets, list) else 0,
            "provider": web_meta.get("provider") or web_meta.get("active_provider"),
            "reason": web_meta.get("reason"),
        }
    return {
        "ok": True,
        "system_prompt": meta.get("system_prompt_preview"),
        "intent_result": meta.get("intent_result"),
        "pipeline_flags": meta.get("pipeline_flags"),
        "web_context_included": web_included,
        "response_meta": meta,
    }


@router.get("/debug/web_status")
async def debug_web_status(
    current = Depends(get_current_user_opt),
):
    if current:
        if str(current.get("role") or "").lower() not in {"creator", "admin"}:
            raise HTTPException(403, "web_status requires creator/admin role")
    else:
        if not _prompt_preview_allowed():
            raise HTTPException(404, "web_status is not available in this environment")
    try:
        pipeline = get_pipeline()
    except Exception as exc:
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, f"Pipeline initialization failed: {exc}") from exc

    enricher = getattr(pipeline, "web_enricher", None)
    return {
        "ok": True,
        "configured": bool(enricher is not None),
        "active_provider": getattr(enricher, "active_provider", None) if enricher else None,
        "provider_order": getattr(enricher, "provider_order", None) if enricher else None,
        "has_serper_key": bool(os.getenv("SERPER_API_KEY")),
    }


@router.post("/debug/web_search")
async def debug_web_search(
    body: WebSearchDebugRequest,
    current = Depends(get_current_user_opt),
):
    if current:
        if str(current.get("role") or "").lower() not in {"creator", "admin"}:
            raise HTTPException(403, "web_search requires creator/admin role")
    else:
        if not _prompt_preview_allowed():
            raise HTTPException(404, "web_search is not available in this environment")
    try:
        pipeline = get_pipeline()
    except Exception as exc:
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, f"Pipeline initialization failed: {exc}") from exc

    enricher = getattr(pipeline, "web_enricher", None)
    if enricher is None:
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, "WebEnricher not configured")

    try:
        prefer_news_provider = str(body.mode or "").strip().lower() == "news"
        source_prefs = None
        if prefer_news_provider and body.user_id and body.country and body.lang:
            try:
                from netapi.core import addressbook
                from netapi import memory_store

                bid = addressbook.get_source_prefs(
                    user_id=int(body.user_id),
                    country=str(body.country),
                    lang=str(body.lang),
                    intent="news",
                )
                blk = memory_store.get_block(bid) if bid else None
                if isinstance(blk, dict):
                    source_prefs = blk.get("meta") or blk
            except Exception:
                source_prefs = None
        results = enricher.web_search(
            body.query,
            lang=body.lang,
            max_results=int(body.max_results),
            country_code=body.country,
            prefer_news_provider=prefer_news_provider,
            source_prefs=source_prefs,
            mode=body.mode,
        )
    except Exception as exc:
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, f"web_search failed: {exc}") from exc

    return {
        "ok": True,
        "query": body.query,
        "provider": getattr(enricher, "_last_provider", None) or getattr(enricher, "active_provider", None),
        "count": len(results or []),
        "results": results,
    }


def _asked_sources_once(user_id: Optional[int], conv_id: Optional[int]) -> bool:
    if user_id is None or conv_id is None:
        return False
    try:
        from netapi.modules.chat import history as chat_history  # type: ignore

        turns = chat_history.load_recent_turns(user_id=int(user_id), conversation_id=int(conv_id), limit=20)
        for t in turns or []:
            if str(t.get("role") or "").lower() not in {"ai", "assistant"}:
                continue
            text = str(t.get("text") or "")
            if "Welche 1-3 Seiten bevorzugst du" in text and "Nachrichten" in text:
                return True
        return False
    except Exception:
        return False


def _looks_like_source_prefs_answer(message: str) -> bool:
    low = (message or "").strip().lower()
    if not low:
        return False
    # quick heuristic: domains, commas, or known preference keywords
    if ".at" in low or ".com" in low or ".de" in low:
        return True
    if "," in low:
        return True
    if any(token in low for token in ("orf", "standard", "apa", "krone", "presse", "serios", "serioes", "keine", "nicht", "ohne")):
        return True
    return False


@router.get("/ping")
def ping():
    """Health check"""
    return {"ok": True, "version": "2.0", "module": "chat-v2"}


@router.get("/stats")
def stats():
    """Get pipeline statistics including learning metrics"""
    try:
        pipeline = get_pipeline()
        reflector = get_reflector()
        learning_hub = get_learning_hub()
        
        has_primary = False
        try:
            if pipeline.llm_primary and hasattr(pipeline.llm_primary, "available"):
                has_primary = bool(pipeline.llm_primary.available())
        except Exception:
            has_primary = False

        mode = "real_llm" if has_primary else "mock_llm"

        return {
            "ok": True,
            "reflection": reflector.get_statistics(),
            "learning": learning_hub.get_statistics() if learning_hub else None,
            "mode": mode,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/feedback")
def add_feedback(
    interaction_id: str,
    feedback: str,  # "positive", "negative", "neutral"
    correction: Optional[str] = None
):
    """
    Add user feedback to improve learning.
    
    Example:
        POST /api/v2/chat/feedback
        {
            "interaction_id": "1729588800",
            "feedback": "positive"
        }
    """
    try:
        learning_hub = get_learning_hub()
        if not learning_hub:
            return {"ok": False, "error": "Learning Hub not available"}
        
        learning_hub.add_feedback(interaction_id, feedback, correction)
        return {"ok": True, "message": "Feedback recorded"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Export router
__all__ = ["router"]
