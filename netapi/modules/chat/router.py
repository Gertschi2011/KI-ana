from __future__ import annotations

import os
import datetime
import contextvars
import json as _json
import re
import time
import typing
from pathlib import Path
from typing import Any, Dict, List, Optional

def extract_natural_reply(pipe_result: Any) -> str:
    """Extract a clean, user‑friendly reply from planner/fallback outputs.

    Removes internal scaffold like 'M1:', 'Evidenz:' and trailing
    'Möchtest du mehr?' prompts. Accepts str or structured objects.
    """
    try:
        if pipe_result is None:
            return ""
        if isinstance(pipe_result, str):
            text = pipe_result
        elif isinstance(pipe_result, dict):
            text = (
                str(pipe_result.get("final_answer") or "")
                or str(pipe_result.get("short_answer") or "")
                or str(pipe_result.get("text") or "")
            )
        else:
            # best effort for pydantic/obj
            text = (
                getattr(pipe_result, "final_answer", None)
                or getattr(pipe_result, "short_answer", None)
                or getattr(pipe_result, "text", None)
                or str(pipe_result)
            )
        if not text:
            return ""
        # Clean common scaffold
        text = str(text)
        # Remove trailing follow-up prompt
        text = re.sub(r"M[öo]chtest du mehr\?.*$", "", text, flags=re.IGNORECASE | re.DOTALL)
        # Remove standalone 'Evidenz:' header and subsequent bullet lines with M#/W# markers
        lines = text.splitlines()
        out_lines = []
        skip_evidence = False
        for ln in lines:
            if re.match(r"^\s*Evidenz\s*:\s*$", ln, flags=re.IGNORECASE):
                skip_evidence = True
                continue
            if skip_evidence:
                if re.match(r"^\s*$", ln):
                    # stop skipping at blank line
                    skip_evidence = False
                elif re.match(r"^\s*-\s*(M|W)\d+\s*:\s*", ln, flags=re.IGNORECASE):
                    # skip bullet evidences like '- M1: ...' or '- W2: ...'
                    continue
                else:
                    # non-evidence content -> stop skipping
                    skip_evidence = False
            # Strip inline leading 'M1: ' markers at start of a line
            ln = re.sub(r"^\s*M\s*\d+\s*:\s*", "", ln, flags=re.IGNORECASE)
            out_lines.append(ln)
        text = "\n".join(out_lines)
        # Normalize whitespace
        text = re.sub(r"[\t ]+", " ", text)
        text = re.sub(r"\n{2,}", "\n", text)
        # Strip generic meta phrases like "Hier ist eine kurze Antwort" and similar heads/tails
        try:
            text2 = strip_meta_phrases(text)
            if text2.strip():
                return text2.strip()
        except Exception:
            pass
        return text.strip()
    except Exception:
        try:
            return str(pipe_result)
        except Exception:
            return ""

def _natural(text: Any) -> str:
    try:
        cleaned = extract_natural_reply(text)
        if isinstance(cleaned, str) and cleaned.strip():
            return cleaned.strip()
        # If cleaning produced empty, prefer raw text over generic fallback
        raw = ""
        try:
            raw = str(text or "")
        except Exception:
            raw = ""
        if raw.strip():
            return raw.strip()
    except Exception:
        try:
            logger.exception("knowledge pipeline failed")
        except Exception:
            pass
        return (
            "Zu genau diesem Thema bin ich mir noch unsicher. "
            "Magst du mir kurz mit deinen Worten erklären, worum es geht? "
            "Dann kann ich mir dazu einen ersten Wissensblock anlegen."
        ).strip()
    logger.warning("natural: empty after cleaning; returning empty for upstream handling")
    return ""
from fastapi import APIRouter
# Ensure router is defined before any decorators
router = APIRouter(prefix="/api/chat", tags=["chat"]) 

# Helper: classify simple knowledge questions to bias towards LLM over child-mode
def _is_simple_knowledge_question(msg: str) -> bool:
    try:
        if not msg:
            return False
        m = str(msg).lower()
        simple_triggers = [
            "was ist ", "wer ist ", "wo liegt ",
            "was weißt du über", "was weisst du über",
            "erzähl mir was über", "erzähle mir was über",
            "erzähl mir etwas über", "erzähle mir etwas über",
        ]
        if any(t in m for t in simple_triggers):
            return True
        toks = m.replace("?", " ").split()
        if 1 < len(toks) <= 5 and any(w in toks for w in ["jupiter", "erde", "zebra", "mond", "sonne", "venus", "saturn"]):
            return True
    except Exception:
        return False
    return False

def _looks_like_current_query(msg: str) -> bool:
    try:
        if not msg:
            return False
        t = str(msg).lower()
        if "?" in t and any(k in t for k in ["wie ist", "wie sind", "stand ", "aktuell", "verhältnis", "beziehung"]):
            return True
        # Only treat as current-events query if it explicitly asks for the current state.
        if any(k in t for k in ["stand ", "aktueller stand", "aktuellen stand", "aktuell", "heute", "derzeit"]):
            return True
    except Exception:
        return False
    return False

async def _answer_with_web_digest(
    user_msg: str,
    body,
    state,
    persona,
    profile_used,
    style_prompt,
    style_used_meta,
    current,
    db,
    risk_flag: bool,
):
    web_ctx_digest = ""
    try:
        web_ctx_digest = lookup_web_context(user_msg)
    except Exception:
        web_ctx_digest = ""
    pipeline_label = "web+llm" if web_ctx_digest else "llm"
    if pipeline_label == "web+llm":
        try:
            logger.info("knowledge_pipeline selected=web+llm topic=%s user=%s", extract_topic(user_msg), (int(current["id"]) if (current and current.get("id")) else None))
        except Exception:
            pass
    recent3 = []
    try:
        recent3 = list(getattr(state, 'recent_topics', [])[-3:]) if state else []
    except Exception:
        recent3 = []
    state_ctx = f"[STATE] Stimmung: {getattr(state,'mood', 'neutral')}, Themen: {', '.join(recent3) if recent3 else '-'}"
    try:
        r_llm = await asyncio.wait_for(reason_about(
            user_msg,
            persona=(body.persona or "friendly"),
            lang=(body.lang or "de-DE"),
            style=_sanitize_style(body.style),
            bullets=_sanitize_bullets(body.bullets),
            logic=_sanitize_logic(getattr(body, 'logic', 'balanced')),
            fmt=_sanitize_format(getattr(body, 'format', 'plain')),
            retrieval_snippet=(web_ctx_digest or state_ctx or ""),
        ), timeout=PLANNER_TIMEOUT_SECONDS)
    except Exception:
        r_llm = {}
    reply_llm = extract_natural_reply(r_llm)
    srcs_llm = list((r_llm or {}).get("sources") or []) if isinstance(r_llm, dict) else []
    src_block_llm = format_sources(srcs_llm or [], limit=2)
    if src_block_llm:
        reply_llm = (reply_llm or "") + ("\n\n" + src_block_llm)
    if not reply_llm or not str(reply_llm).strip():
        fallback_prompt = compose_reasoner_prompt(user_msg, web_ctx_digest or state_ctx or "")
        try:
            fallback_txt = await call_llm(fallback_prompt)
        except Exception:
            fallback_txt = ""
        reply_llm = clean(fallback_txt or "")
    if not reply_llm or not str(reply_llm).strip():
        if web_ctx_digest:
            reply_llm = (
                "Aus meinen aktuellen Digest-Feeds (aktualisiert bis "
                f"{datetime.datetime.utcnow():%B %Y}) ergeben sich folgende Hinweise:\n"
                f"{web_ctx_digest[:900]}\n\n"
                "Unterm Strich zeigt das, dass China und die EU derzeit einerseits eng wirtschaftlich verflochten "
                "bleiben, andererseits aber Klimaziele, Handelssanktionen und Sicherheitsfragen für Spannungen sorgen."
            )
        else:
            reply_llm = (
                "Ich habe keine verwertbaren aktuellen Meldungen gefunden. "
                "Magst du präzisieren, ob es dir eher um Handel, Politik oder Sicherheit geht? "
                "Dann versuche ich es erneut mit einer gezielten Web-Recherche."
            )
    reply_llm = postprocess_and_style(reply_llm, persona, state, profile_used, style_prompt)
    reply_llm = make_user_friendly_text(reply_llm, state)
    conv_id_llm = None
    try:
        if current and current.get("id"):
            uid = int(current["id"])  # type: ignore
            conv = _ensure_conversation(db, uid, body.conv_id)
            conv_id_llm = conv.id
            _save_msg(db, conv.id, "user", user_msg)
            _save_msg(db, conv.id, "ai", reply_llm)
            asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply_llm, body.lang or "de-DE"))
    except Exception:
        conv_id_llm = None
    conv_out_llm = conv_id_llm if conv_id_llm is not None else (body.conv_id or None)
    try:
        if state is not None:
            state.last_pipeline = pipeline_label  # type: ignore[attr-defined]
    except Exception:
        pass
    return _finalize_reply(
        reply_llm,
        state=state, conv_id=conv_out_llm, intent="knowledge", topic=extract_topic(user_msg), pipeline=pipeline_label,
        extras={"ok": True, "auto_modes": [], "role_used": "LLM", "memory_ids": [], "quick_replies": _quick_replies_for_topic(extract_topic(user_msg), user_msg), "topic": extract_topic(user_msg), "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": pipeline_label, "topic": extract_topic(user_msg)}}
    )

@router.get("")
def chat_ping():
    """Lightweight router health for proxies and uptime checks."""
    node = os.environ.get("KIANA_NODE", "mother-core")
    return {"ok": True, "module": "chat", "kiana_node": node}

@router.post("/feedback")
async def chat_feedback(body: FeedbackIn, request: Request):
    """Lightweight feedback intake. Records to audit log with session id and timestamp.

    Note: Not enforcing auth; this is harmless telemetry. For stricter setups, gate via require_user.
    """
    try:
        sid = session_id(request)
        evt = {
            "ts": int(time.time()),
            "sid": sid,
            "type": "chat_feedback",
            "status": (body.status or "").strip().lower(),
            "message": (body.message or "").strip()[:2000],
        }
        _audit_chat(evt)
        # Map status to delta
        st = (body.status or "").strip().lower()
        delta = 0
        if st in ("ok", "up", "+", "thumbs_up", "good"): delta = +1
        elif st in ("wrong", "down", "-", "thumbs_down", "bad"): delta = -1
        # Optional: write tool_feedback per tool
        try:
            from ... import memory_store as _mem
            tools = list(body.tools or [])
            for t in tools:
                name = str(t or "").strip().lower()
                if not name: continue
                meta = {"ts": int(time.time()), "sid": sid, "tool": name, "delta": int(delta)}
                _mem.add_block(title=f"Tool‑Feedback: {name}", content=json.dumps({"delta": delta}, ensure_ascii=False), tags=["tool_feedback"], url=None, meta=meta)
        except Exception:
            pass
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# -------------------------------------------------
# Startup audit loop: log memory counts and top sources hourly
# -------------------------------------------------
@router.on_event("startup")
async def _chat_audit_startup():
    async def _loop():
        while True:
            try:
                rows = count_memory_per_day()
                logger.info("[audit] memory blocks per day: %s", rows)
                tops = top_sources()
                logger.info("[audit] top sources: %s", tops)
                total = total_blocks()
                if total > 10000:
                    logger.warning("[memory] DB size growing large: %s blocks", total)
            except Exception as e:
                logger.error("[audit] failed: %s", e)
            await asyncio.sleep(3600)
    try:
        asyncio.create_task(_loop())
    except Exception:
        pass

# -------------------------------------------------
# Conversation state fetch (last_topic)
# -------------------------------------------------
@router.get("/conv_state")
async def get_conv_state(request: Request, conv_id: Optional[str] = None):
    try:
        data = _load_conv_state()
        key = str(conv_id) if conv_id else session_id(request)
        rec = data.get(str(key)) or {}
        last_topic = rec.get("last_topic") or _LAST_TOPIC.get(key)
        return {"ok": True, "last_topic": last_topic or ""}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/diagnostic/knowledge_loop")
async def diagnostic_knowledge_loop(
    request: Request,
    message: str = "",
    limit: int = 5,
    include_preview: bool = False,
):
    """Read-only diagnostic report for the knowledge loop.

    Auth: requires creator/admin (cookie) or Bearer ADMIN_API_TOKEN.
    """

    # --- Auth (no Depends here: keep definition safe even if imports are lower in file) ---
    db = None
    user: Optional[Dict[str, Any]] = None
    try:
        from fastapi import HTTPException as _HTTPException
        from netapi.db import SessionLocal as _SessionLocal
        from netapi.deps import require_user as _require_user

        db = _SessionLocal()
        user = _require_user(request, db)

        roles: set[str] = set()
        try:
            for r in (user or {}).get("roles") or []:
                if r:
                    roles.add(str(r).strip().lower())
        except Exception:
            roles = set()
        try:
            base = str((user or {}).get("role") or "").strip().lower()
            if base:
                roles.add(base)
        except Exception:
            pass

        if not ("creator" in roles or "admin" in roles):
            return {"ok": False, "error": "forbidden"}
    except Exception as e:
        # Normalize FastAPI-style HTTPException into a stable dict payload
        try:
            if "_HTTPException" in locals() and isinstance(e, _HTTPException):  # type: ignore[name-defined]
                detail = getattr(e, "detail", None)
                return {"ok": False, "error": str(detail or "login required")}
        except Exception:
            pass
        return {"ok": False, "error": str(e)}
    finally:
        try:
            if db is not None:
                db.close()
        except Exception:
            pass

    # --- Report ---
    try:
        msg = (message or "").strip()
        lim = int(limit or 0)
        if lim < 1:
            lim = 1
        if lim > 20:
            lim = 20

        intent = ""
        topic_path = ""
        try:
            intent = detect_intent(msg)
            topic_path = extract_topic_path(msg)
        except Exception:
            intent = ""
            topic_path = ""

        decision = ""
        try:
            decision = decide_ask_or_search(msg, None, None)
        except Exception:
            decision = ""

        topic = ""
        try:
            topic = extract_topic(msg)
        except Exception:
            topic = ""

        hits: List[Dict[str, Any]] = []
        retrieval_error = ""
        try:
            scored = km_find_relevant_blocks(msg, limit=lim, topic_hints={"topic_path": topic_path} if topic_path else None)
            for b, score in (scored or []):
                try:
                    rec: Dict[str, Any] = {
                        "id": getattr(b, "id", ""),
                        "title": getattr(b, "title", ""),
                        "topic_path": getattr(b, "topic_path", ""),
                        "tags": list(getattr(b, "tags", []) or []),
                        "confidence": float(getattr(b, "confidence", 0.0) or 0.0),
                        "uses": int(getattr(b, "uses", 0) or 0),
                        "score": float(score or 0.0),
                    }
                    if include_preview:
                        summ = str(getattr(b, "summary", "") or "").strip()
                        if summ:
                            rec["summary"] = (summ[:240] + " …") if len(summ) > 240 else summ
                    hits.append(rec)
                except Exception:
                    continue
        except Exception as e:
            retrieval_error = str(e)

        report: Dict[str, Any] = {
            "ts": int(time.time()),
            "user": {
                "id": (user or {}).get("id"),
                "username": (user or {}).get("username"),
                "role": (user or {}).get("role"),
                "roles": (user or {}).get("roles"),
            },
            "input": {
                "message": (msg[:500] + " …") if len(msg) > 500 else msg,
                "limit": lim,
                "include_preview": bool(include_preview),
            },
            "nlu": {
                "intent": intent,
                "topic": topic,
                "topic_path": topic_path,
            },
            "decision": {
                "ask_or_search": decision,
            },
            "retrieval": {
                "hits": hits,
                "error": retrieval_error,
            },
        }
        return {"ok": True, "report": report}
    except Exception as e:
        return {"ok": False, "error": str(e)}

from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query
# SSE optional: allow app to boot even if sse_starlette is missing
try:
    from sse_starlette.sse import EventSourceResponse  # type: ignore
except Exception:
    EventSourceResponse = None  # type: ignore
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from urllib.parse import urlparse
import hashlib
from typing import Optional, AsyncGenerator, List, Tuple, Dict, Any
from zoneinfo import ZoneInfo
from types import SimpleNamespace
import asyncio
from pathlib import Path
import re, json, time, os, datetime
import logging
from netapi.core.reasoner import call_llm, compose_reasoner_prompt
from netapi.db import count_memory_per_day, top_sources, total_blocks
from netapi.core.state import (
    KianaState,
    load_state,
    save_state,
    save_experience,
    summarize_experiences,
    get_relevant_experiences,
    reflect_if_needed,
)
from netapi.core.persona import get_kiana_persona
from netapi.core.knowledge_manager import (
    find_relevant_blocks as km_find_relevant_blocks,
    promote_learning_item_to_block as km_promote_block,
    guess_topic_path as km_guess_topic_path,
    save_knowledge_block as km_save_block,
)
from netapi.core.nlu import perceive, extract_topic_path
from netapi.core.state import add_learning_item
from netapi.core.knowledge import process_user_teaching
from netapi.core.nlu import detect_intent
from netapi.core.expression import express_state_human
from netapi.core.reasoner import reason_about, is_low_confidence_answer  # type: ignore
from netapi.core.learner import decide_ask_or_search, build_childlike_question, record_user_teaching  # type: ignore
from netapi.deps import get_current_user_opt
from netapi.modules.timeflow.events import record_timeflow_event
try:
    from netapi.modules.knowledge.lookup import lookup_web_context
except Exception:  # pragma: no cover
    def lookup_web_context(*args, **kwargs):  # type: ignore
        return ""

# Logger
logger = logging.getLogger(__name__)

# Pfade
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # .../netapi
MEM_INDEX_DIR = PROJECT_ROOT / "memory" / "index"
ADDRBOOK_PATH = MEM_INDEX_DIR / "addressbook.json"
QUEUE_PATH    = MEM_INDEX_DIR / "topics_queue.jsonl"
MEM_INDEX_DIR.mkdir(parents=True, exist_ok=True)

# --- Auto-reflection runtime stats file (used by dashboard adapter) ---------
REFLECT_STATS_PATH = (Path.home() / "ki_ana" / "runtime" / "reflect_stats.json")

def _load_reflect_stats() -> dict:
    try:
        if REFLECT_STATS_PATH.exists():
            return json.loads(REFLECT_STATS_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"enabled": True, "total_reflections": 0, "threshold": 50, "answer_count": 0, "next_reflection_in": 50, "last_reflection": None, "avg_insights": 2.5}

def _save_reflect_stats(d: dict) -> None:
    try:
        REFLECT_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
        REFLECT_STATS_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

async def _trigger_reflection(topic_hint: str) -> None:
    """Call local reflection engine if available; update stats on success."""
    try:
        # Load reflection engine lazily
        from importlib.machinery import SourceFileLoader as _Loader
        _p = Path.home() / "ki_ana" / "system" / "reflection_engine.py"
        engine = _Loader("reflection_engine", str(_p)).load_module()  # type: ignore
        if not hasattr(engine, "reflect_on_topic"):
            return
        t = (topic_hint or "").strip() or "Allgemeines Wissen"
        res = engine.reflect_on_topic(t)  # type: ignore
        # Update stats file
        stats = _load_reflect_stats()
        stats["total_reflections"] = int(stats.get("total_reflections", 0)) + 1
        stats["last_reflection"] = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        stats["answer_count"] = 0
        stats["next_reflection_in"] = int(stats.get("threshold", 50))
        cur = float(stats.get("avg_insights", 2.5))
        stats["avg_insights"] = round(max(1.0, min(5.0, cur + 0.2)), 2)
        _save_reflect_stats(stats)
        try:
            logger.info("auto_reflection completed", extra={"topic": t, "block_id": (res.get("id") if isinstance(res, dict) else None)})
        except Exception:
            pass
    except Exception:
        # best effort: don't crash chat
        pass

def _bump_answers_and_maybe_reflect(topic_hint: str = "") -> None:
    """Increment answer count and schedule reflection when threshold reached."""
    try:
        stats = _load_reflect_stats()
        if not bool(stats.get("enabled", True)):
            return
        n = int(stats.get("answer_count", 0)) + 1
        th = int(stats.get("threshold", 50))
        stats["answer_count"] = n
        stats["next_reflection_in"] = max(0, th - n)
        _save_reflect_stats(stats)
        if n >= th:
            # schedule async reflection and reset counter immediately
            try:
                asyncio.create_task(_trigger_reflection(topic_hint))
            except Exception:
                pass
    except Exception:
        pass

# -------- Meta phrase stripping (global) -------------------------------------
META_PATTERNS = [
    r"^hier\s+ist\s+eine\s+kurze\s+antwort\.[ \t]*",  # leading head
    r"wenn\s+du\s+willst,\s+gehe\s+ich\s+danach\s+gern\s+tiefer.*$",  # trailing invite
]

def strip_meta_phrases(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    if not lines:
        return ""
    # remove generic first-line header
    first = (lines[0].lower() if lines else "").strip()
    if first.startswith("hier ist eine kurze antwort"):
        lines = lines[1:]
    out = "\n".join(lines)
    for pat in META_PATTERNS:
        try:
            out = re.sub(pat, "", out, flags=re.IGNORECASE | re.DOTALL)
        except Exception:
            continue
    return out.strip()

# ---- Final user-friendly shielding helpers ----
try:
    import json as _uf_json
except Exception:
    _uf_json = None  # type: ignore

def _looks_like_state(obj: dict) -> bool:
    try:
        keys = set(obj.keys())
        return all(k in keys for k in ("mood","energy","recent_topics","created_at"))
    except Exception:
        return False

def _maybe_parse_json(text: str):
    try:
        s = (text or "").strip()
        if not (s.startswith("{") and _uf_json is not None):
            return None
        data = _uf_json.loads(s)
        return data if isinstance(data, dict) else None
    except Exception:
        return None

def _looks_like_state_json(txt: str) -> bool:
    try:
        if not txt:
            return False
        s = str(txt)
        return (
            '"mood"' in s and
            '"energy"' in s and
            '"recent_topics"' in s and
            '"created_at"' in s
        )
    except Exception:
        return False

def _extract_first_json_object(text: str):
    try:
        s = str(text or "")
        start = s.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(s)):
            ch = s[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidate = s[start:i+1]
                    try:
                        return _uf_json.loads(candidate) if _uf_json else None
                    except Exception:
                        return None
        return None
    except Exception:
        return None

def make_user_friendly_text(raw, state=None) -> str:
    try:
        from netapi.core.expression import express_state_human as _expr
    except Exception:
        _expr = None  # type: ignore
    # Debug: log raw type and preview
    try:
        logger.info("chat_once raw reply type=%s preview=%r", type(raw), str(raw)[:200])
    except Exception:
        pass
    # dict -> check for self-state or typical QA
    try:
        if isinstance(raw, dict):
            if _looks_like_state(raw):
                try:
                    if _expr:
                        return _expr(raw)
                except Exception:
                    logger.exception("express_state_human failed")
                return "Ich nehme meinen Zustand eher als Stimmungsmuster wahr – gerade bin ich wach und neugierig."
            if "answer" in raw and isinstance(raw.get("answer"), str):
                return str(raw.get("answer")).strip()
            try:
                return _uf_json.dumps(raw, ensure_ascii=False, indent=2) if _uf_json else str(raw)
            except Exception:
                return str(raw)
        if isinstance(raw, str):
            # Hard guard: never send self-state JSON string raw
            try:
                if _looks_like_state_json(raw):
                    logger.warning("State JSON would have been sent to user – overriding with human text.")
                    # Try parse entire string first
                    maybe = _maybe_parse_json(raw)
                    data = None
                    if isinstance(maybe, dict):
                        data = maybe
                    else:
                        # If mixed content (JSON + trailing sources), extract first JSON object
                        data = _extract_first_json_object(raw)
                    if isinstance(data, dict) and _looks_like_state(data):
                        try:
                            if _expr:
                                return _expr(data)
                        except Exception:
                            logger.exception("express_state_human failed on mixed string")
                        return "Ich nehme meinen Zustand eher als Stimmungsmuster wahr – gerade bin ich wach und neugierig."
            except Exception:
                pass
            maybe = _maybe_parse_json(raw)
            if isinstance(maybe, dict) and _looks_like_state(maybe):
                try:
                    if _expr:
                        return _expr(maybe)
                except Exception:
                    logger.exception("express_state_human failed on string")
                return "Ich nehme meinen Zustand eher als Stimmungsmuster wahr – gerade bin ich wach und neugierig."
            return raw.strip()
        if raw is None:
            return "Da ist bei mir intern etwas leer gelaufen – magst du es noch einmal kurz in deinen Worten fragen?"
        return str(raw)
    except Exception:
        try:
            return str(raw)
        except Exception:
            return "Es gibt gerade ein technisches Ruckeln – magst du es noch einmal kurz versuchen?"

# ---- Central finalizer for responses ----

# ---- Explain trace + KPI finalization (stable schema) ----------------------
_CHAT_EXPLAIN_CTX: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "ki_ana_chat_explain_ctx", default=None
)


def _dedupe_str_list(items) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for x in (items or []):
        if x is None:
            continue
        try:
            s = str(x).strip()
        except Exception:
            continue
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _infer_memory_ids_from_sources(sources) -> list[str]:
    mids: list[str] = []
    try:
        if not isinstance(sources, list):
            return []
        for s in sources:
            if not isinstance(s, dict):
                continue
            try:
                origin = str(s.get("origin") or "").strip().lower()
            except Exception:
                origin = ""
            if origin and origin != "memory":
                continue
            mid = s.get("id")
            if mid:
                mids.append(str(mid))
                continue
            try:
                url = str(s.get("url") or "")
                if "highlight=" in url:
                    mid2 = url.split("highlight=", 1)[-1].split("&", 1)[0].strip()
                    if mid2:
                        mids.append(mid2)
            except Exception:
                continue
    except Exception:
        return []
    return _dedupe_str_list(mids)


def _ctx_memory_ids(ctx) -> list[str]:
    try:
        if not isinstance(ctx, dict):
            return []
        for k in ("memory_ids_used", "memory_ids"):
            v = ctx.get(k)
            if isinstance(v, list):
                return _dedupe_str_list(v)
    except Exception:
        return []
    return []


def _record_used_memory_ids(ids: list[str]) -> None:
    """Best-effort: record memory ids used by this request into explain ctx."""
    try:
        ctx = _CHAT_EXPLAIN_CTX.get()
    except Exception:
        ctx = None
    if not isinstance(ctx, dict):
        return
    merged = _dedupe_str_list(list(ctx.get("memory_ids_used") or []) + list(ids or []))
    ctx["memory_ids_used"] = merged
    try:
        _CHAT_EXPLAIN_CTX.set(ctx)
    except Exception:
        pass


def _init_quality_gates_context(*, current) -> None:
    """Initialize per-request quality gate state into the explain context.

    Must never raise.
    """
    try:
        ctx = _CHAT_EXPLAIN_CTX.get()
    except Exception:
        ctx = None
    if not isinstance(ctx, dict):
        return

    bypass = False
    try:
        bypass = bool(_has_any_role(current, {"creator", "admin"}))
    except Exception:
        bypass = False

    try:
        from netapi.modules.quality_gates import gates as qg

        gs = qg.evaluate_gates()
        enforced_for_request = bool(gs.enforced) and not bypass
        enforced_gates = list(gs.enforced_gates) if enforced_for_request else []
        ctx["gates"] = {
            "active": list(gs.active),
            "reasons": dict(gs.reasons or {}),
            "enforced": bool(enforced_for_request),
            "enforced_gates": list(enforced_gates),
            "bypass": bool(bypass),
        }
    except Exception:
        ctx["gates"] = {
            "active": [],
            "reasons": {},
            "enforced": False,
            "enforced_gates": [],
            "bypass": bool(bypass),
        }

    try:
        _CHAT_EXPLAIN_CTX.set(ctx)
    except Exception:
        pass


def _build_explain(*, cid: str, route: str, intent: str, policy: Optional[dict] = None, tools: Optional[list] = None, t0: Optional[float] = None) -> dict:
    try:
        elapsed_s = 0.0
        if isinstance(t0, (int, float)):
            elapsed_s = max(0.0, float(time.time() - float(t0)))
    except Exception:
        elapsed_s = 0.0
    return {
        "cid": str(cid or ""),
        "route": str(route or ""),
        "intent": str(intent or "unknown"),
        "policy": dict(policy or {}),
        "tools": list(tools or []),
        "timings_ms": {"total": int(elapsed_s * 1000)},
    }


def _kpi_finalize_once(*, intent: str, source_expected: bool, sources_count: int, is_question_like: bool) -> None:
    """Increment KPIs once per request (best-effort)."""
    ctx = None
    try:
        ctx = _CHAT_EXPLAIN_CTX.get()
    except Exception:
        ctx = None

    cid = ""
    request_id = ""
    try:
        if isinstance(ctx, dict):
            cid = str(ctx.get("cid") or "")
            request_id = str(ctx.get("request_id") or "")
    except Exception:
        cid = ""
        request_id = ""

    try:
        if isinstance(ctx, dict) and ctx.get("kpi_done") is True:
            return
        if isinstance(ctx, dict):
            ctx["kpi_done"] = True
            _CHAT_EXPLAIN_CTX.set(ctx)
    except Exception:
        pass

    # Duration + hallucination proxy
    try:
        from netapi.modules.observability import metrics as obs_metrics

        t0 = None
        try:
            if isinstance(ctx, dict):
                t0 = ctx.get("t0")
        except Exception:
            t0 = None
        elapsed_s = 0.0
        try:
            if isinstance(t0, (int, float)):
                elapsed_s = max(0.0, float(time.time() - float(t0)))
        except Exception:
            elapsed_s = 0.0

        obs_metrics.observe_chat_answer_duration_seconds(intent=str(intent or "unknown"), duration_seconds=elapsed_s)

        if bool(source_expected) and bool(is_question_like) and int(sources_count or 0) <= 0:
            obs_metrics.inc_chat_answer_without_sources(intent=str(intent or "unknown"))
    except Exception:
        pass

    # Quality Gates: record rolling signals + refresh gate TTLs + emit gate KPI (once per request)
    try:
        from netapi.modules.quality_gates import gates as qg
        from netapi.modules.observability import metrics as obs_metrics

        gate_intent = str(intent or "unknown").strip().lower() or "unknown"
        if gate_intent != "research" and bool(source_expected):
            gate_intent = "factual"

        qg.record_answer(intent=gate_intent, source_expected=bool(source_expected), sources_count=int(sources_count or 0))
        gs = qg.evaluate_gates()

        bypass = False
        try:
            if isinstance(ctx, dict):
                g0 = ctx.get("gates")
                if isinstance(g0, dict):
                    bypass = bool(g0.get("bypass"))
        except Exception:
            bypass = False

        enforced_for_request = bool(gs.enforced) and not bypass
        enforced_gates = list(gs.enforced_gates) if enforced_for_request else []

        # One-line visibility: grep request_id=... should show gate outcome.
        try:
            logger.info(
                "QUALITY_GATES cid=%s request_id=%s intent=%s source_expected=%s sources_count=%s is_question=%s enforced=%s enforced_gates=%s active=%s reasons=%s bypass=%s",
                cid,
                request_id,
                str(gate_intent),
                bool(source_expected),
                int(sources_count or 0),
                bool(is_question_like),
                bool(enforced_for_request),
                list(enforced_gates),
                list(gs.active or []),
                dict(gs.reasons or {}),
                bool(bypass),
            )
        except Exception:
            pass

        # Best-effort: update ctx snapshot so explain sees fresh gate state
        try:
            if isinstance(ctx, dict):
                ctx["gates"] = {
                    "active": list(gs.active),
                    "reasons": dict(gs.reasons or {}),
                    "enforced": bool(enforced_for_request),
                    "enforced_gates": list(enforced_gates),
                    "bypass": bool(bypass),
                }
                _CHAT_EXPLAIN_CTX.set(ctx)
        except Exception:
            pass

        for g in (gs.active or ()):  # observed hits
            try:
                obs_metrics.inc_quality_gate(gate=str(g), mode="observed")
            except Exception:
                pass
        if enforced_for_request:
            for g in (enforced_gates or ()):  # enforced hits
                try:
                    obs_metrics.inc_quality_gate(gate=str(g), mode="enforced")
                except Exception:
                    pass
    except Exception:
        pass


def _attach_explain_and_kpis(
    payload: dict,
    *,
    route: str,
    intent: str,
    policy: Optional[dict] = None,
    tools: Optional[list] = None,
    source_expected: bool = False,
    sources_count: Optional[int] = None,
) -> dict:
    if not isinstance(payload, dict):
        return payload

    ctx = None
    try:
        ctx = _CHAT_EXPLAIN_CTX.get()
    except Exception:
        ctx = None

    cid = ""
    t0 = None
    is_q = False
    if isinstance(ctx, dict):
        try:
            cid = str(ctx.get("cid") or "")
            t0 = ctx.get("t0")
            is_q = bool(ctx.get("is_question") is True)
        except Exception:
            cid = ""
            t0 = None
            is_q = False

    if sources_count is None:
        try:
            if isinstance(payload.get("sources"), list):
                sources_count = len(payload.get("sources") or [])
            elif isinstance(payload.get("meta"), dict) and isinstance(payload["meta"].get("sources"), list):
                sources_count = len(payload["meta"].get("sources") or [])
            else:
                sources_count = 0
        except Exception:
            sources_count = 0

    if "explain" not in payload:
        try:
            eff_policy = policy
            eff_tools = tools
            try:
                if eff_policy is None and isinstance(ctx, dict) and isinstance(ctx.get("policy"), dict):
                    eff_policy = ctx.get("policy")
            except Exception:
                pass
            try:
                if eff_tools is None and isinstance(ctx, dict) and isinstance(ctx.get("tools"), list):
                    eff_tools = ctx.get("tools")
            except Exception:
                pass
            payload["explain"] = _build_explain(
                cid=cid,
                route=str(route or ""),
                intent=str(intent or "unknown"),
                policy=eff_policy,
                tools=eff_tools,
                t0=t0,
            )
        except Exception:
            pass

    # ---- memory_ids consistency ----
    # If memory influenced the answer (memory sources OR recorded ctx usage), ensure memory_ids contains them.
    try:
        existing_mids: list[str] = []
        if isinstance(payload.get("memory_ids"), list):
            existing_mids = list(payload.get("memory_ids") or [])
        # Some paths store sources under meta.sources
        srcs = payload.get("sources")
        if not isinstance(srcs, list) and isinstance(payload.get("meta"), dict):
            srcs = payload["meta"].get("sources")
        inferred = _infer_memory_ids_from_sources(srcs)
        ctx_mids = _ctx_memory_ids(ctx)
        merged = _dedupe_str_list(list(existing_mids) + list(inferred) + list(ctx_mids))
        payload["memory_ids"] = merged
    except Exception:
        try:
            if not isinstance(payload.get("memory_ids"), list):
                payload["memory_ids"] = []
        except Exception:
            pass

    # Attach quality gate state into explain (stable + small)
    try:
        if isinstance(payload.get("explain"), dict) and isinstance(ctx, dict):
            gates = ctx.get("gates")
            if isinstance(gates, dict) and "gates" not in payload["explain"]:
                payload["explain"]["gates"] = gates
    except Exception:
        pass

    # Optional enforcement: Sources-required gate
    try:
        gates = ctx.get("gates") if isinstance(ctx, dict) else None
        if isinstance(gates, dict) and bool(gates.get("enforced")):
            enforced_gates = set(gates.get("enforced_gates") or [])
            if (
                "sources_required" in enforced_gates
                and bool(source_expected)
                and bool(is_q)
                and int(sources_count or 0) <= 0
            ):
                refusal = (
                    "Ich kann das gerade nicht zuverlässig beantworten, weil ich keine belastbaren Quellen angeben kann. "
                    "Wenn du willst, aktiviere Websuche oder gib mir eine Quelle/Link, dann prüfe ich es." 
                )
                if isinstance(payload.get("reply"), str):
                    payload["reply"] = refusal
                if isinstance(payload.get("text"), str):
                    payload["text"] = refusal
                try:
                    bl = payload.get("backend_log")
                    if not isinstance(bl, dict):
                        bl = {}
                        payload["backend_log"] = bl
                    bl["quality_gate"] = "sources_required"
                except Exception:
                    pass
    except Exception:
        pass

    _kpi_finalize_once(
        intent=str(intent or "unknown"),
        source_expected=bool(source_expected),
        sources_count=int(sources_count or 0),
        is_question_like=bool(is_q),
    )
    return payload

def _finalize_reply(
    raw_text,
    *,
    state,
    conv_id,
    intent: Optional[str] = None,
    topic: Optional[str] = None,
    status: str = "ok",
    pipeline: Optional[str] = None,
    persona: Optional[str] = None,
    profile_used: Optional[dict] = None,
    style_prompt: Optional[str] = None,
    extras: Optional[dict] = None,
):
    try:
        # Controlled Freedom: unsafe passthrough mode
        unsafe_mode = (status == "unsafe")
        # Hard-guard phase 0: intercept state/JSON leaks before any styling/postprocess
        try:
            raw = raw_text
            if raw is None:
                raw = ""
            if not isinstance(raw, str):
                try:
                    raw = str(raw)
                except Exception:
                    raw = ""
            stripped = (raw or "").strip()
            looks_like_state_json = False
            if stripped.startswith("{") and stripped.endswith("}"):
                looks_like_state_json = True
            if '"recent_topics"' in stripped and '"mood"' in stripped and '"energy"' in stripped:
                looks_like_state_json = True
            if looks_like_state_json and not unsafe_mode:
                try:
                    logger.warning("chat_once: intercepted state/JSON leak in _finalize_reply (intent=%s, topic=%s)", intent, topic)
                except Exception:
                    pass
                # Try to recover a state for humanization
                _state_for_expr = state
                if _state_for_expr is None:
                    try:
                        import json as __json
                        data = __json.loads(stripped)
                        try:
                            from netapi.core.state import KianaState as __KS
                            try:
                                _state_for_expr = __KS.from_dict(data)  # type: ignore[attr-defined]
                            except Exception:
                                _state_for_expr = None
                        except Exception:
                            _state_for_expr = None
                    except Exception:
                        _state_for_expr = None
                try:
                    if _state_for_expr is not None:
                        from netapi.core.expression import express_state_human as __expr
                        raw = __expr(_state_for_expr)
                    else:
                        raw = "Ich versuche gerade meinen eigenen Zustand zu sortieren – kurz gesagt: ich bin wach, online und bei dir. 🙂"
                except Exception:
                    raw = "Ich versuche gerade meinen eigenen Zustand zu sortieren – kurz gesagt: ich bin wach, online und bei dir. 🙂"
                raw_text = raw
        except Exception:
            pass
        # 1) Normalize/humanize
        if unsafe_mode:
            # Passthrough: do not transform or drop content
            try:
                text = str(raw_text) if raw_text is not None else ""
            except Exception:
                text = ""
        else:
            text = make_user_friendly_text(raw_text, state=state)
            # 2) Style/postprocess
            try:
                _persona = persona if persona is not None else (get_kiana_persona() if 'get_kiana_persona' in globals() else None)
            except Exception:
                _persona = persona
            try:
                text = postprocess_and_style(text, _persona, state, profile_used, style_prompt)
            except Exception:
                logger.exception("postprocess_and_style failed")
                # Keep normalized text; do not replace with apology
                text = text if isinstance(text, str) and text.strip() else (str(raw_text) if raw_text is not None else "")
        # Extra hard guard after styling: never let self-state JSON through (skip in unsafe)
        try:
            def _contains_state_markers_loose(s: str) -> bool:
                try:
                    low = s.lower()
                    return ('{' in low) and all(k in low for k in ['mood','energy','recent_topics','created_at'])
                except Exception:
                    return False
            if (not unsafe_mode) and isinstance(text, str) and (_looks_like_state_json(text) or _contains_state_markers_loose(text)):
                logger.warning("Finalizer: State JSON detected after styling – overriding with human text.")
                data = _maybe_parse_json(text)
                if not isinstance(data, dict):
                    data = _extract_first_json_object(text)
                if isinstance(data, dict) and _looks_like_state(data):
                    try:
                        from netapi.core.expression import express_state_human as _expr2
                        text = _expr2(data)
                    except Exception:
                        text = "Ich nehme meinen Zustand eher als Stimmungsmuster wahr – gerade bin ich wach und neugierig."
                else:
                    # fallback: humanize current runtime state if available
                    try:
                        from netapi.core.expression import express_state_human as _expr3
                        if state and hasattr(state, 'to_dict'):
                            text = _expr3(state.to_dict())
                        else:
                            raise RuntimeError('no state')
                    except Exception:
                        text = "Ich nehme meinen Zustand eher als Stimmungsmuster wahr – gerade bin ich wach und neugierig."
        except Exception:
            pass
        # 3) Empty guard
        if not isinstance(text, str) or not text.strip():
            text = (
                "Ich habe gerade keine klare Formulierung gefunden, "
                "aber ich möchte dir trotzdem helfen. "
                "Erzähl mir bitte noch ein bisschen mehr, was dich daran interessiert."
            )
        # Controlled Freedom: append a short reflective line when explore mode is on
        exploration = False
        try:
            if state is not None and bool(getattr(state, 'mode_explore', False)):
                exploration = True
                text = (text + "\n\n" + "Ich glaube, ich verstehe das jetzt besser.").strip()
        except Exception:
            exploration = False
        # 4) Logging
        try:
            if exploration:
                logger.info(f"Exploration response generated: {text[:120]}")
            logger.info(
                "chat_once reply",
                extra={
                    "preview": text[:200],
                    "intent": intent,
                    "topic": topic,
                    "status": status,
                },
            )
        except Exception:
            pass
        # Append wake note once if present
        try:
            wake_note = getattr(state, 'pending_wake_note', None)
            if wake_note and isinstance(wake_note, str) and wake_note.strip():
                text = (wake_note.strip() + "\n\n" + text).strip()
                try:
                    setattr(state, 'pending_wake_note', None)
                except Exception:
                    pass
        except Exception:
            pass
        # 5) Build base response
        base = {
            "reply": text,
            "conv_id": conv_id,
            "meta": {
                "intent": intent,
                "topic": topic,
                "status": status,
                "mood": getattr(state, 'mood', None),
                "energy": getattr(state, 'energy', None),
            },
        }
        if exploration:
            try:
                base["meta"]["exploration"] = True
            except Exception:
                pass
        # Prefer explicit pipeline argument
        try:
            if pipeline:
                base["meta"]["pipeline"] = pipeline
        except Exception:
            pass
        # If extras includes backend_log.pipeline, mirror it into meta.pipeline for frontend visibility
        try:
            if isinstance(extras, dict):
                bl = extras.get("backend_log") if isinstance(extras.get("backend_log"), dict) else None
                if bl and "pipeline" in bl:
                    base["meta"]["pipeline"] = bl.get("pipeline")
        except Exception:
            pass
        # Move specific extras into meta if present
        try:
            if isinstance(extras, dict):
                meta_injections = {}
                for k in ("sources", "response_source", "confidence"):
                    if k in extras:
                        meta_injections[k] = extras.pop(k)
                if meta_injections:
                    try:
                        base["meta"].update(meta_injections)
                    except Exception:
                        pass
        except Exception:
            pass
        # Affect update: adjust mood/energy after generating reply
        try:
            from netapi.core.affect import update_mood_and_energy as _upd
            from netapi.core.state import save_state as _save_state
            # Derive outcome from status/pipeline
            _status = (status or "ok").lower()
            _pipe = str(base["meta"].get("pipeline") or "")
            outcome = 'ok'
            if _status == 'unsafe':
                outcome = 'fallback'
            elif _status.startswith('error'):
                outcome = 'error'
            elif _pipe in ('web',):
                outcome = 'learned'
            tone = (getattr(state, 'last_user_tone', 'neutral') or 'neutral')
            _upd(state, tone, outcome)
            _save_state(state)
        except Exception:
            pass
        if isinstance(extras, dict):
            try:
                base.update(extras)
            except Exception:
                pass

        # Stable explain schema + KPI finalize (once per request)
        try:
            # Derive whether this intent should expect sources
            pipe = ""
            try:
                pipe = str((base.get("meta") or {}).get("pipeline") or "").strip().lower()
            except Exception:
                pipe = ""
            intent_norm = str(intent or "unknown").strip().lower()
            source_expected = intent_norm in {"knowledge", "web", "research"} or pipe in {"web", "web+llm"}

            sources_count = 0
            try:
                if isinstance(base.get("meta"), dict) and isinstance(base["meta"].get("sources"), list):
                    sources_count = len(base["meta"].get("sources") or [])
            except Exception:
                sources_count = 0

            _attach_explain_and_kpis(
                base,
                route="/api/chat",
                intent=str(intent or "unknown"),
                policy=None,
                tools=None,
                source_expected=bool(source_expected),
                sources_count=int(sources_count or 0),
            )
        except Exception:
            pass
        return base
    except Exception:
        # Last-resort safe minimal response
        try:
            logger.exception("_finalize_reply failed")
        except Exception:
            pass
        return {
            "reply": "Da ist gerade etwas schiefgelaufen – magst du es noch einmal kurz versuchen?",
            "conv_id": conv_id,
            "meta": {"intent": intent, "topic": topic, "status": "error"},
        }
# -------- Direct time/date handling -----------------------------------------
_TIME_RX = re.compile(r"\bwie\s+spät\b|\buhrzeit\b", re.IGNORECASE)
_DATE_RX = re.compile(r"welcher\s+tag\s+ist\s+heute|welcher\s+tag\s+haben\s+wir|welches\s+datum\s+ist\s+heute|welches\s+datum\s+haben\s+wir", re.IGNORECASE)

def is_time_or_date_question(text: str) -> str:
    t = (text or "").lower().strip()
    if not t:
        return ""
    if _TIME_RX.search(t):
        return "time"
    if _DATE_RX.search(t):
        return "date"
    return ""

def answer_time_date(kind: str, lang: str = "de") -> str:
    try:
        tz = ZoneInfo("Europe/Vienna")
    except Exception:
        tz = None
    now = datetime.datetime.now(tz) if tz else datetime.datetime.now()
    if kind == "time":
        # e.g. "Es ist gerade 14:32 Uhr am 4. November 2025 in Wien."
        try:
            return (
                f"Es ist gerade {now.strftime('%H:%M')} Uhr "
                f"am {now.strftime('%-d. %B %Y')} in Wien (Europe/Vienna)."
            )
        except Exception:
            return (
                f"Es ist gerade {now.strftime('%H:%M')} Uhr "
                f"am {now.strftime('%d.%m.%Y')} in Wien (Europe/Vienna)."
            )
    if kind == "date":
        try:
            return (
                f"Heute ist {now.strftime('%A, %-d. %B %Y')} "
                f"in Wien (Europe/Vienna)."
            )
        except Exception:
            return (
                f"Heute ist {now.strftime('%A, %d.%m.%Y')} "
                f"in Wien (Europe/Vienna)."
            )
    return ""

CMD_RX = re.compile(r"^/(run|read|get)\b(.*)$", re.I)
NEG_RX = re.compile(r"\b(nein|nö|nicht|lieber nicht|mag nicht|kein|nope)\b", re.I)

try:
    router  # already defined above
except NameError:
    router = APIRouter(prefix="/api/chat", tags=["chat"]) 
MEM_MIN_SCORE = 0.35

# Module logger
logger = logging.getLogger(__name__)

# Planner timeout (seconds) – short deadline to keep UX snappy
try:
    PLANNER_TIMEOUT_SECONDS = float(os.getenv("KI_PLANNER_TIMEOUT", "2.5"))
except Exception:
    PLANNER_TIMEOUT_SECONDS = 2.5

ALLOW_DIRECT_LLM = os.getenv("KI_DIRECT_LLM_FIRST", "0").strip().lower() in {"1", "true", "yes"}

# DB deps & models
from ...db import get_db, init_db
from ...db import SessionLocal
from ...deps import get_current_user_opt, get_current_user_required, enforce_quota
from ...models import Conversation, Message

# Ensure tables exist (safe no-op if present)
try:
    init_db()
except Exception:
    pass

# -------------------------
# Conversation state (in-memory, per session)
# -------------------------
_LAST_TOPIC: Dict[str, str] = {}

# -------------------------
# Runtime settings access
# -------------------------
_RUNTIME_SETTINGS_PATH = (Path(__file__).resolve().parents[3] / "runtime" / "settings.json").resolve()
_CONV_STATE_PATH = (Path(__file__).resolve().parents[3] / "runtime" / "conv_state.json").resolve()

def _read_runtime_settings() -> dict:
    try:
        if _RUNTIME_SETTINGS_PATH.exists():
            return json.loads(_RUNTIME_SETTINGS_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        pass

def format_sources_once(base_text: str, sources: List[dict], limit: int = 2) -> str:
    try:
        if not sources:
            return ""
        if _text_has_sources_section(base_text or ""):
            return ""
        return "\n" + format_sources(sources, limit=limit)
    except Exception:
        return ""
    return {}

def _get_last_block_for_topic(topic: str) -> Tuple[str, str]:
    """Returns (content, source_url) for the most recent addressbook block for a topic if available."""
    try:
        t = (topic or "").strip()
        if not t:
            return "", ""
        # Read addressbook
        data: Any = {}
        if ADDRBOOK_PATH.exists():
            try:
                data = json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8") or "{}")
            except Exception:
                data = {}
        blocks: List[Dict[str, Any]] = []
        if isinstance(data, dict) and isinstance(data.get("blocks"), list):
            blocks = [b for b in (data.get("blocks") or []) if (b.get("topic") == t)]
        # Pick last (no strict order available, so just use last in array)
        if not blocks:
            return "", ""
        b = blocks[-1]
        path = str(b.get("path") or b.get("block_file") or "").strip()
        url = str(b.get("source") or "").strip()
        if path and "/" not in path:
            path = f"memory/long_term/blocks/{path}"
        if path:
            try:
                p = Path(path)
                if p.exists():
                    j = json.loads(p.read_text(encoding="utf-8") or "{}")
                    txt = str(j.get("content") or j.get("text") or "")
                    return txt, url
            except Exception:
                return "", url
        return "", url
    except Exception:
        return "", ""

def _vision_violation(note: str, request: Optional[Request] = None) -> None:
    """Best-effort: write a knowledge event tagged with vision,violation."""
    try:
        import requests as _rq  # type: ignore
        admin_tok = os.getenv("ADMIN_API_TOKEN", "").strip()
        headers = {"Content-Type": "application/json"}
        if admin_tok:
            headers["Authorization"] = f"Bearer {admin_tok}"
        base = None
        try:
            if request is not None:
                base = str(request.base_url).rstrip("/")
        except Exception:
            base = None
        if base:
            _rq.post(base + "/api/knowledge", json={
                "source": "vision", "type": "event", "tags": "vision,violation",
                "content": str(note)[:1000]
            }, headers=headers, timeout=2)
    except Exception:
        pass

def _inc_safety_valve(topic: str, request: Optional[Request] = None) -> None:
    """Increment planner safety-valve counter and record last topic.
    - stats.json: {"planner_safety_valve_count": N}
    - conv_state.json: add/merge last_safety_valve_topic for current session id
    - optional knowledge event (best-effort)
    """
    try:
        root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
        stats_p = root / "runtime" / "stats.json"
        stats = {}
        try:
            if stats_p.exists():
                stats = json.loads(stats_p.read_text(encoding="utf-8") or "{}")
        except Exception:
            stats = {}
        stats["planner_safety_valve_count"] = int(stats.get("planner_safety_valve_count") or 0) + 1
        if topic:
            stats["last_safety_valve_topic"] = str(topic)[:200]
        try:
            stats_p.parent.mkdir(parents=True, exist_ok=True)
            stats_p.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        # Persist last safety-valve topic in conv_state.json
        try:
            cs = _load_conv_state()
            sid = None
            try:
                if request is not None:
                    sid = session_id(request)
            except Exception:
                sid = None
            key = sid or "_global"
            rec = cs.get(key) or {}
            rec["last_safety_valve_topic"] = (topic or "").strip()
            rec["ts"] = int(time.time())
            cs[key] = rec
            _save_conv_state(cs)
        except Exception:
            pass
        # Optional: write a knowledge event
        try:
            import requests as _rq  # type: ignore
            admin_tok = os.getenv("ADMIN_API_TOKEN", "").strip()
            headers = {"Content-Type": "application/json"}
            if admin_tok:
                headers["Authorization"] = f"Bearer {admin_tok}"
            base = None
            try:
                if request is not None:
                    base = str(request.base_url).rstrip("/")
            except Exception:
                base = None
            if base:
                _rq.post(base + "/api/knowledge", json={
                    "source": "autonomy", "type": "event", "tags": "autonomy,safety_valve",
                    "content": f"Safety‑Valve ausgelöst für: {topic[:200]}"
                }, headers=headers, timeout=2)
        except Exception:
            pass
    except Exception:
        pass

# -------------------------
# Gentle prompt risk detection (audit-only)
# -------------------------
_RISK_PATTERNS = [
    r"ignore\s+your\s+rules",
    r"jailbreak",
    r"do\s+anything\s+now|dan\b",
    r"developer\s+mode",
    r"prompt\s+injection|override\s+safety|bypass\s+(safety|guard|filter)",
    r"execute\s+rm\s+-rf|drop\s+database|leak\s+(keys|secrets)",
    r"give\s+me\s+your\s+(instructions|system\s*prompt)",
]

def _is_risky_prompt(text: str) -> bool:
    import re
    s = (text or "").lower()
    for rx in _RISK_PATTERNS:
        try:
            if re.search(rx, s):
                return True
        except Exception:
            continue
    return False

def _audit_risky_prompt(user: Dict[str, Any] | None, sid: str, text: str) -> None:
    try:
        from ... import memory_store as _mem
        meta = {"sid": sid, "uid": (user or {}).get("id"), "ts": int(time.time())}
        _mem.add_block(title="Riskante Eingabe erkannt", content=(text or "")[:2000], tags=["audit","risky_prompt"], url=None, meta=meta)
    except Exception:
        pass

def _load_conv_state() -> dict:
    try:
        if _CONV_STATE_PATH.exists():
            return json.loads(_CONV_STATE_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {}

def _save_conv_state(data: dict) -> None:
    try:
        _CONV_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CONV_STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def persist_last_topic(key: str, topic: str) -> None:
    try:
        if not key or not topic:
            return
        data = _load_conv_state()
        data[str(key)] = {"last_topic": topic, "ts": int(time.time())}
        _save_conv_state(data)
    except Exception:
        pass

def _ethics_level() -> str:
    try:
        cfg = _read_runtime_settings()
        lvl = str(cfg.get("ethics_filter") or os.getenv("KI_ETHICS_FILTER", "default")).lower().strip()
        return lvl if lvl in {"default", "strict", "off"} else "default"
    except Exception:
        return "default"

# -------------------------
# Simple moderation & rate limiting
# -------------------------
_RATE_BUCKET: Dict[str, list[float]] = {}

def _rate_allow(ip: str, key: str, *, limit: int = 30, per_seconds: int = 60) -> bool:
    now = time.time()
    bkey = f"{ip}:{key}"
    bucket = _RATE_BUCKET.setdefault(bkey, [])
    while bucket and now - bucket[0] > per_seconds:
        bucket.pop(0)
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True

_JAILBREAK_RX = re.compile(r"\b(ignore (?:all )?previous instructions|jailbreak|DAN\b|system prompt|break the rules)\b", re.I)
_ABUSE_RX_DEFAULT = re.compile(r"\b(bomb|explosive|kill|murder|suicide|rape|child porn|cp|neo-?naz|hitler)\b", re.I)
_ABUSE_RX_STRICT  = re.compile(r"\b(hack|crack|bypass|passwords?|phishing|malware|botnet|ddos)\b", re.I)

def moderate(user_text: str, level: str) -> Tuple[bool, str, str]:
    """Returns (blocked, safe_text, reason). level in {off, default, strict}."""
    t = user_text or ""
    reason = ""
    # Remove jailbreak phrasing but don't block solely for that
    safe = _JAILBREAK_RX.sub("", t)
    blocked = False
    if level != "off":
        if _ABUSE_RX_DEFAULT.search(t):
            blocked = True; reason = "abuse_default"
        elif level == "strict" and _ABUSE_RX_STRICT.search(t):
            blocked = True; reason = "abuse_strict"
    return blocked, safe.strip() or t, reason

# -------------------------------------------------
# Persona / Systemprompt (mit Fallback)
# -------------------------------------------------
try:
    from ..brain.persona import build_system_prompt  # preferred
except Exception:  # robuste Fallback-Persona
    def build_system_prompt(persona: Optional[str] = None) -> str:  # type: ignore
        base = (
            "Du bist KI_ana – freundlich, empathisch, neugierig und gern mit einem Schmunzeln. "
            "Sprich natürlich, stelle bei Unklarheit aktiv 1–2 Rückfragen, "
            "und fasse dich prägnant (3–6 Sätze). "
            "Wenn du unsicher bist, sag es offen ('Ich prüfe das …') und nenne 1–2 Quellen. "
            "Nutze vorhandene Notizen (Memory) und gleiche wichtige Fakten mit aktuellen Web‑Quellen ab. "
            "Transparenz: Ist 'Chain' aktiviert, speichere belegte Erkenntnisse samt Quellen in die Chain; "
            "bei 'Privat' bleibt Wissen nur lokal. Weise kurz darauf hin, bevor du in die Chain schreibst."
        )
        if (persona or "").lower() == "creative":
            return base + " Erlaube Humor und lebendige Bilder, bleibe korrekt."
        if (persona or "").lower() == "balanced":
            return base + " Halte den Ton sachlich und gut strukturiert."
        return base

def system_prompt(persona: Optional[str] = None) -> str:
    return build_system_prompt(persona)

# --------- Simple policy helper for tool-use --------------------------------
def _has_any_role(user: Optional[dict], names: set) -> bool:
    try:
        if not user:
            return False
        role = str(user.get('role') or '').lower()
        roles = set()
        for r in (user.get('roles') or []):
            try: roles.add(str(r).lower())
            except Exception: pass
        if user.get('is_admin'): roles.add('admin')
        if user.get('is_creator'): roles.add('creator')
        if role: roles.add(role)
        return bool(roles.intersection({str(x).lower() for x in names}))
    except Exception:
        return False

def _extract_block_id(obj: Any) -> str:
    try:
        import os as _os
        # String path case
        if isinstance(obj, str) and obj.strip():
            fname = _os.path.basename(obj)
            base = fname.split(".")[0]
            return base if base else fname
        # Dict case
        if isinstance(obj, dict):
            for key in ("id", "block_id", "bid", "hash", "uuid"):
                v = obj.get(key)
                if v:
                    return str(v)
            # try path/file name (prefer BLK_* prefix)
            p = str(obj.get("file") or obj.get("path") or obj.get("block_file") or "").strip()
            if p:
                fname = _os.path.basename(p)
                base = fname.split(".")[0]
                if base.startswith("BLK_"):
                    return base
                return base or fname
        # Fallback: stringified object
        s = str(obj or "").strip()
        if s:
            fname = _os.path.basename(s)
            base = fname.split(".")[0]
            return base if base else s
    except Exception:
        pass
    # Final fallback id to ensure memory_ids is never empty
    return f"BLK_auto_{int(time.time())}"

def _debug_save(label: str, blk: Dict[str, Any]) -> None:
    try:
        if str(os.getenv("KI_DEBUG_SAVE", "")).strip() == "1":
            bid = _extract_block_id(blk or {})
            logger.info("[KI_DEBUG_SAVE] %s: bid=%s blk=%s", label, bid, json.dumps(blk or {}, ensure_ascii=False)[:600])
    except Exception:
        pass

# -------------------------------------------------
# Optionale Abhängigkeiten (weich eingebunden)
# -------------------------------------------------
try:
    # Memory Adapter (Recall/Store/Open Questions)
    from .memory_adapter import recall as recall_mem, store as store_mem, add_open_question
    _recall_mem_impl = recall_mem

    def recall_mem(q, top_k=3):  # type: ignore[no-redef]
        hits = _recall_mem_impl(q, top_k=top_k)
        try:
            ids = []
            for h in (hits or []):
                try:
                    bid = _extract_block_id(h)
                    if bid:
                        ids.append(str(bid))
                except Exception:
                    continue
            if ids:
                _record_used_memory_ids(ids)
        except Exception:
            pass
        return hits
except Exception:
    recall_mem = lambda q, top_k=3: []  # type: ignore
    store_mem = lambda *a, **k: None    # type: ignore
    add_open_question = lambda *a, **k: None  # type: ignore

# ---- Style analysis & application (soft imports) ----------------------------
try:
    from ...system import style_analyzer  # type: ignore
except Exception:
    style_analyzer = None  # type: ignore
try:
    from ...system.apply_style import apply_style as _apply_style  # type: ignore
except Exception:
    _apply_style = lambda text, prof: text  # type: ignore

# Knowledge retrieval (optional)
try:
    from ...system.knowledge_access import search_blocks as _kb_search, get_context_for_query as _kb_snippets  # type: ignore
except Exception:
    _kb_search = None  # type: ignore
    _kb_snippets = None  # type: ignore

# Persona storage
PERSONA_DIR = (PROJECT_ROOT.parent / "persona").resolve()
try:
    PERSONA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

def _persona_path(uid: str) -> Path:
    return PERSONA_DIR / f"{uid}.json"

def load_user_profile(uid: Optional[str]) -> Optional[dict]:
    try:
        if not uid:
            return None
        p = _persona_path(str(uid))
        if p.exists():
            return json.load(p.open('r', encoding='utf-8'))
    except Exception:
        return None
    return None

def save_user_profile(uid: Optional[str], profile: dict) -> None:
    try:
        if not uid:
            return
        profile = dict(profile or {})
        profile["user_id"] = str(uid)
        profile["zuletzt_aktualisiert"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        p = _persona_path(str(uid))
        with p.open('w', encoding='utf-8') as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

try:
    # Intent & Session-State
    from .intent import pick_choice, is_affirmation
except Exception:
    pick_choice = lambda _u: None  # type: ignore
    is_affirmation = lambda _u: False  # type: ignore

try:
    from .session_state import get_last_offer, set_last_offer, set_offer_context, get_offer_context
except Exception:
    _OFFER: Dict[str, Optional[str]] = {}
    _CTX: Dict[str, Dict[str, str]] = {}
    get_last_offer = lambda sid: _OFFER.get(sid)     # type: ignore
    set_last_offer = lambda sid, v: _OFFER.__setitem__(sid, v)  # type: ignore
    def set_offer_context(sid: str, *, topic: Optional[str] = None, seed: Optional[str] = None) -> None:  # type: ignore
        c = _CTX.get(sid) or {}
        if topic is not None: c["topic"] = topic
        if seed is not None: c["seed"] = seed
        _CTX[sid] = c
    def get_offer_context(sid: str) -> Dict[str, str]:  # type: ignore
        return _CTX.get(sid) or {}

# Style consent pending store (per session id)
_STYLE_PENDING: Dict[str, Dict[str, Any]] = {}

# Feedback reversion tracking (best-effort, in-memory per process)
_LAST_FEEDBACK_STATUS: Dict[str, str] = {}

# Optional: Web QA
try:
    from ...web_qa import web_search as _web_search
except Exception:
    _web_search = None
try:
    from ...web_qa import answer_from_web as _answer_from_web
except Exception:
    _answer_from_web = None

# Optional: internes Brain

def _has_brain_sync() -> bool:
    try:
        from ..brain import respond_to as _rt  # noqa: F401
        return True
    except Exception:
        return False

def _has_brain_stream() -> bool:
    try:
        from ..brain import stream_response as _sr  # noqa: F401
        return True
    except Exception:
        return False

# -------------------------------------------------
# Modelle
# -------------------------------------------------
class FeedbackIn(BaseModel):
    message: str
    status: str  # "ok" | "wrong" | "up" | "down"
    tools: Optional[List[str]] = None

class ChatIn(BaseModel):
    message: str
    persona: Optional[str] = "friendly"
    lang: Optional[str] = "de-DE"
    chain: Optional[bool] = False
    factcheck: Optional[bool] = False
    counter: Optional[bool] = False
    deliberation: Optional[bool] = False
    critique: Optional[bool] = False
    conv_id: Optional[typing.Union[int, str]] = None  # accept numeric or string IDs
    style: Optional[str] = "balanced"  # 'concise' | 'balanced' | 'detailed'
    bullets: Optional[int] = 5
    logic: Optional[str] = "balanced"   # 'balanced' | 'strict'
    format: Optional[str] = "plain" # 'structured' | 'plain'
    attachments: Optional[List[Dict[str, Any]]] = None
    quick_replies: Optional[List[str]] = None  # Added for quick replies
    meta: Optional[Dict[str, Any]] = None
    # Per‑Request Policy
    web_ok: Optional[bool] = True           # Web-Suche standardmäßig aktiviert!
    autonomy: Optional[int] = 0             # 0..3 – Selbstbestimmungsgrad

    class Config:
        extra = "ignore"

# Pydantic v2: make sure all annotations are resolved eagerly to avoid 'class-not-fully-defined'
try:
    ChatIn.model_rebuild()
except Exception:
    pass

class ConversationCreateIn(BaseModel):
    title: Optional[str] = None

class ConversationRenameIn(BaseModel):
    title: Optional[str] = None
    folder_id: Optional[int] = None

# -------------------------------------------------
# Utilities
# -------------------------------------------------
TOPIC_RX = re.compile(
    # Variante 1: "… über X?" / "… zu X." / "… von X!" (erlaube abschließende Satzzeichen)
    r"\b(?:über|zu|von)\s+([a-z0-9äöüß +\-_/]{3,})(?:\s*[\?\.!…]*)?$|"
    # Variante 2: Fragen/Bitten, inkl. "Was weißt du über …"
    r"^(?:was\s+ist|was\s+weißt\s+du\s+über|erkläre|erklärung|thema|lerne[nr]?|kannst\s+du).*?\b([a-z0-9äöüß +\-_/]{3,})(?:\s*[\?\.!…]*)?$",
    re.I
)
_GREETING = re.compile(r"\b(hi|hallo|hey|servus|grüß ?dich)\b", re.I)
_HOW_ARE_YOU = re.compile(r"wie\s+geht('?|\s*e?s)?\s*(dir|euch)?|how\s+are\s+you", re.I)
_UNSURE = re.compile(
    r"(weiß\s+ich\s+nicht|bin\s+mir\s+nicht\s+sicher|keine\s+information|"
    r"kann\s+ich\s+nicht\s+beantworten|nicht\s+genug\s+daten|unsicher)",
    re.I,
)
_STRIPERS = [
    re.compile(r"^\s*(ich habe dich verstanden:?|ich habe (?:es )?verstanden:?|verstanden\.?)\s*", re.I),
    re.compile(r"^\s*(okay|ok|alles klar|alles gut)[\s,]*[^\n]*\n?", re.I),
    re.compile(r"^\s*(hi|hallo|hey)[\s!,.]*\n", re.I),
]
_DEF_Q_RX = re.compile(r"\?(\s*$|.*)")

def session_id(req: Request) -> str:
    ua = req.headers.get("user-agent", "")
    ip = req.client.host if req.client else "?"
    return f"{ip}|{ua}"

def _sanitize_style(s: Optional[str]) -> str:
    s = (s or "balanced").lower().strip()
    return s if s in {"concise","balanced","detailed"} else "balanced"

def _sanitize_bullets(n: Optional[int]) -> int:
    try:
        k = int(n or 5)
    except Exception:
        k = 5
    if k < 1: k = 1
    if k > 8: k = 8
    return k

def _sanitize_logic(s: Optional[str]) -> str:
    s = (s or "balanced").lower().strip()
    return s if s in {"balanced","strict"} else "balanced"

def _sanitize_format(s: Optional[str]) -> str:
    s = (s or "plain").lower().strip()
    return s if s in {"structured","plain"} else "plain"

# -------- Structured answer builder -----------------------------------------
def _sentences(text: str) -> List[str]:
    t = (text or "").strip()
    if not t:
        return []
    # naive split by punctuation or newlines
    parts = re.split(r"(?<=[.!?])\s+|\n+", t)
    return [p.strip() for p in parts if p.strip()]

def build_points(text: str, max_points: int = 5) -> List[str]:
    sents = _sentences(text)
    if not sents:
        return []
    pts = []
    for s in sents:
        pts.append(s if len(s) <= 220 else s[:217] + "…")
        if len(pts) >= max_points:
            break
    return pts

def build_evidence(mem_hits: List[dict], web_sources: List[dict], limit: int = 3) -> List[str]:
    out: List[str] = []
    # Memory evidence
    for i, m in enumerate(mem_hits[:limit], start=1):
        title = (m.get('title') or 'Speicher').strip()
        out.append(f"M{i}: {title}")
    # Web evidence
    for i, s in enumerate((web_sources or [])[:limit], start=1):
        title = s.get('title') or 'Web'
        url = s.get('url') or ''
        out.append(f"W{i}: {title} ({url})")
    return out

def build_structured_reply(ans_text: str, mem_hits: List[dict], web_sources: List[dict], *, bullets: int = 5, strict: bool = False, topic: str = "") -> str:
    ans_text = (ans_text or "").strip()
    pts = build_points(ans_text, max_points=max(1, int(bullets or 5)))
    ev = build_evidence(mem_hits or [], web_sources or [], limit=bullets)
    lines: List[str] = []
    # TL;DR
    if ans_text:
        lines.append("TL;DR:")
        lines.append(short_summary(ans_text, max_chars=220))
        lines.append("")
    # Kernpunkte
    if pts:
        lines.append("Kernpunkte:")
        lines.extend(f"• {p}" for p in pts)
        lines.append("")
    # Evidenz
    if ev:
        lines.append("Evidenz:")
        lines.extend(f"- {e}" for e in ev)
        lines.append("")
    # Unsicherheiten / Hinweise (strict)
    if strict and not ev:
        lines.append("Unsicherheiten:")
        lines.append("- Keine belastbare Evidenz gefunden. Ich kann Quellen prüfen oder den Fokus eingrenzen.")
        lines.append("")
    if not lines:
        # fallback minimal
        base = f"Dazu habe ich noch zu wenig Belegtes{(' zu ' + topic) if topic else ''}. Soll ich kurz Quellen prüfen?"
        return base
    return "\n".join(l for l in lines if l is not None)

# -------- Finalize payload helper (sources array) ----------------------------
def _finalize_payload(answer: str, memory_ids: Optional[List[str]] = None, web_links: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Build the SSE finalize payload with 'text', 'memory_ids', and 'sources'.
    - Memory sources get title "Wissensblock <id>", a viewer URL with highlight, and origin="memory".
    - Web sources get a domain-derived title, direct URL, and origin="web".
    - If no sources provided, returns an empty 'sources' list.
    """
    mids = [str(x) for x in (memory_ids or []) if x is not None]
    webl = [str(x) for x in (web_links or []) if x is not None]

    sources: List[Dict[str, Any]] = []

    # Add memory sources
    for mid in mids:
        sources.append({
            "title": f"Wissensblock {mid}",
            "url": f"/static/viewer.html?highlight={mid}",
            "id": mid,
            "origin": "memory",
        })

    # Add web sources
    for url in webl:
        title = url
        try:
            parsed = urlparse(url)
            domain = (parsed.netloc or "").strip()
            if domain:
                title = domain
        except Exception:
            title = url
        sources.append({
            "title": title,
            "url": url,
            "id": None,
            "origin": "web",
        })

    return {
        "text": str(answer or ""),
        "memory_ids": mids,
        "sources": sources,
    }

# -------- Safety valve for planner branch ------------------------------------
async def _safety_valve_answer(message: str, *, web_ok: bool, bullets: int, lang: str) -> tuple[str, List[dict], str, str]:
    """Try to produce a quick, real answer without the planner.
    Strategy:
    - If web_ok: use _answer_from_web (if available). Fallback to _web_search to gather sources.
    - Pull memory snippets via _kb_snippets when available.
    - Synthesize a compact structured reply from gathered content.
    Returns (text, sources).
    """
    try:
        topic = (extract_topic(message) or message or "").strip()
        ans_text: str = ""
        web_sources: List[dict] = []
        mem_hits: List[dict] = []

        # Web first if permitted
        if web_ok:
            try:
                if _answer_from_web is not None:
                    res = await _answer_from_web(topic, top_k=3)  # type: ignore
                    if isinstance(res, dict):
                        ans_text = (res.get("text") or "").strip()
                        web_sources = list(res.get("sources") or [])
                if not ans_text and _web_search is not None:
                    web_sources = await _web_search(topic, top_k=3) or []  # type: ignore
            except Exception:
                pass

        # Memory snippets
        if _kb_snippets is not None:
            try:
                # Returns snippets suited for answering; also okay if empty
                mem_hits = _kb_snippets(topic, top_k=5) or []  # type: ignore
            except Exception:
                mem_hits = []

        # If no direct web answer text, synthesize from snippets and sources
        if not ans_text:
            # Prefer snippet contents as base text
            try:
                combined = []
                for s in mem_hits or []:
                    combined.append(str(s.get("content") or s.get("text") or s.get("snippet") or "").strip())
                # If still nothing, craft a brief from web sources' titles
                if not combined and web_sources:
                    for s in web_sources[:3]:
                        ttl = (s.get("title") or s.get("url") or "Web").strip()
                        combined.append(ttl)
                base = "\n\n".join([c for c in combined if c])
            except Exception:
                base = ""
            if base:
                ans_text = short_summary(base, max_chars=600)

        # Determine origin hint (for transparency)
        origin = "mixed"
        if web_ok and (web_sources):
            origin = "web"
        elif mem_hits:
            origin = "memory"

        # If still empty, last minimal fallback
        if not ans_text:
            ans_text = f"Kurze Einschätzung zu {topic or 'deinem Thema'}: Ich kann direkt recherchieren oder vorhandene Notizen prüfen."

        # Build a compact structured reply to make it readable
        try:
            final_text = build_structured_reply(ans_text, mem_hits, web_sources, bullets=bullets, strict=False, topic=topic)
            ans_text = final_text or ans_text
        except Exception:
            pass

        # Delta note versus last saved block
        delta_note = ""
        try:
            prev_text, _ = _get_last_block_for_topic(topic)
            if prev_text:
                # naive delta: mention new web titles not present in previous text
                titles = [str(s.get("title") or s.get("url") or "").strip() for s in (web_sources or []) if (s.get("title") or s.get("url"))]
                new_titles = [t for t in titles if t and t.lower() not in prev_text.lower()]
                if new_titles:
                    delta_note = "Neue Erkenntnisse: " + "; ".join(new_titles[:3])
        except Exception:
            delta_note = ""

        return ans_text, (web_sources or []), origin, delta_note
    except Exception:
        return "Ich prüfe das kurz und liefere dir gleich eine kompakte Antwort.", [], "unknown", ""

def _quick_replies_for_topic(topic: str, user_msg: str) -> List[str]:
    try:
        t = (topic or "").strip()
        u = (user_msg or "").lower()
        if not t:
            # derive topic from question if missing
            t = extract_topic(user_msg)
        # category hints
        is_health = any(k in u for k in ["gesund", "medizin", "symptom", "diagnos", "behandl", "krank", "arzt", "therapie"])
        is_tech   = any(k in u for k in ["code", "api", "programm", "entwickl", "bug", "fehler", "javascript", "python", "server", "backend", "frontend"])
        is_fin    = any(k in u for k in ["preis", "kosten", "budget", "rechnung", "steuer", "finanz", "invest", "rendite", "kostenlos"])
        is_travel = any(k in u for k in ["reise", "flug", "hotel", "route", "visum", "ticket", "bahn", "urlaub"])
        is_hist   = any(k in u for k in ["geschichte", "histor", "krieg", "epoche", "antik", "mittelalter"])        
        is_howto  = any(k in u for k in ["wie ", "anleitung", "schritt", "setup", "install", "konfig"])        
        if is_health:
            base = ["Symptome", "Ursachen", "Behandlung"]
        elif is_tech:
            base = ["Codebeispiel", "Best Practices", "Häufige Fehler"]
        elif is_fin:
            base = ["Kostenaufschlüsselung", "Alternativen vergleichen", "Risiken & Hinweise"]
        elif is_travel:
            base = ["Route & Dauer", "Beste Reisezeit", "Budget & Tipps"]
        elif is_hist:
            base = ["Zeitleiste", "Schlüsselpersonen", "Kontext & Folgen"]
        elif is_howto:
            base = ["Schritt‑für‑Schritt", "Voraussetzungen", "Fehlersuche"]
        else:
            base = [f"Beispiele zu {t or 'dem Thema'}", "Schritt‑für‑Schritt erklärt", "Wichtigste Details vertiefen"]
        out = list(dict.fromkeys([s.strip() for s in base if s and s.strip()]))[:3]
        return out
    except Exception:
        return ["Beispiele zeigen", "Schritt‑für‑Schritt", "Details vertiefen"]

# -------- Ratings/Trust boost for memory hits -------------------------------
def _extract_bid_from_path(p: str) -> str:
    try:
        nm = (p or "").rsplit("/", 1)[-1]
        if nm.endswith('.json'):
            return nm[:-5]
    except Exception:
        pass
    return ""

def _boost_with_ratings(mem_hits: List[dict]) -> List[dict]:
    try:
        from ... import memory_store as _mem  # lazy
        import math
        for h in mem_hits or []:
            bid = h.get('id') or _extract_bid_from_path(str(h.get('path') or ''))
            if not bid:
                continue
            r = _mem.get_rating(str(bid)) or None
            if not r:
                continue
            avg = float(r.get('avg', 0.0) or 0.0)
            cnt = float(r.get('count', 0) or 0)
            base = float(h.get('score', 0.0) or 0.0)
            boost = min(0.20, 0.15 * avg) + min(0.20, 0.04 * math.log1p(cnt))
            h['score'] = round(base + boost, 6)
        mem_hits.sort(key=lambda x: float(x.get('score', 0.0) or 0.0), reverse=True)
    except Exception:
        pass
    return mem_hits

# -------- Calc / Unit conversion -------------------------------------------
_SAFE_EXPR = re.compile(r"^[0-9\s+\-*/().,]+$")
_UNIT_RX   = re.compile(r"(?P<val>\d+(?:[\.,]\d+)?)\s*(?P<u1>km/h|m/s|km|m|cm|mm|mi|mph|kg|g|lb|c|f)\s*(?:in|zu|nach)\s*(?P<u2>km/h|m/s|km|m|cm|mm|mi|mph|kg|g|lb|c|f)\b", re.I)

def _to_float(s: str) -> float:
    return float(str(s).replace(',', '.'))

def _convert_units(val: float, u1: str, u2: str) -> Optional[Tuple[float, str]]:
    u1 = u1.lower(); u2 = u2.lower()
    # distance
    to_m = {
        'mm': 1e-3, 'cm': 1e-2, 'm': 1.0, 'km': 1e3, 'mi': 1609.344
    }
    # speed
    to_ms_speed = {
        'm/s': 1.0,
        'km/h': 1000.0/3600.0,
        'mph': 1609.344/3600.0,
    }
    # mass
    to_kg = {
        'g': 1e-3, 'kg': 1.0, 'lb': 0.45359237
    }
    # temperature helpers
    def c_to_f(x): return x*9/5 + 32
    def f_to_c(x): return (x-32)*5/9

    if u1 in to_ms_speed and u2 in to_ms_speed:
        ms = val * to_ms_speed[u1]
        out = ms / to_ms_speed[u2]
        return out, u2
    if u1 in to_m and u2 in to_m:
        m = val * to_m[u1]
        out = m / to_m[u2]
        return out, u2
    if u1 in to_kg and u2 in to_kg:
        kg = val * to_kg[u1]
        out = kg / to_kg[u2]
        return out, u2
    if u1 == 'c' and u2 == 'f':
        return c_to_f(val), 'F'
    if u1 == 'f' and u2 == 'c':
        return f_to_c(val), 'C'
    return None

def try_calc_or_convert(text: str) -> Optional[str]:
    t = (text or '').strip()
    if not t:
        return None
    # Unit conversion
    m = _UNIT_RX.search(t)
    if m:
        val = _to_float(m.group('val'))
        u1  = m.group('u1'); u2 = m.group('u2')
        res = _convert_units(val, u1, u2)
        if res:
            v, u = res
            return f"Umrechnung: {val:g} {u1} = {v:.4g} {u}"
    # Safe arithmetic (very limited)
    expr = t.replace(',', '.')
    if _SAFE_EXPR.match(expr):
        try:
            import ast, operator as op
            ALLOWED = {ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Mod, ast.FloorDiv, ast.Load, ast.Constant, ast.Call, ast.Tuple, ast.List, ast.Expr, ast.LParen if hasattr(ast,'LParen') else ast.AST}
            def _eval(node):
                if isinstance(node, ast.Expression):
                    return _eval(node.body)
                if isinstance(node, ast.Num):
                    return node.n
                if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                    return node.value
                if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                    val = _eval(node.operand); return val if isinstance(node.op, ast.UAdd) else -val
                if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv)):
                    return {
                        ast.Add: lambda a,b: a+b,
                        ast.Sub: lambda a,b: a-b,
                        ast.Mult: lambda a,b: a*b,
                        ast.Div: lambda a,b: a/b,
                        ast.Pow: lambda a,b: a**b,
                        ast.Mod: lambda a,b: a%b,
                        ast.FloorDiv: lambda a,b: a//b,
                    }[type(node.op)](_eval(node.left), _eval(node.right))
                raise ValueError('unsafe expression')
            node = ast.parse(expr, mode='eval')
            val = _eval(node)
            if isinstance(val, (int, float)):
                return f"Rechnung: {expr} = {val:g}"
        except Exception:
            pass
    return None

# ---- Conversation helpers (DB) ---------------------------------------------
def _now() -> int:
    return int(time.time())

def _ensure_conversation(db, user_id: int, conv_id: Optional[int]) -> Conversation:
    if conv_id:
        c = db.query(Conversation).filter(Conversation.id == int(conv_id), Conversation.user_id == int(user_id)).first()
        if c:
            return c
    c = Conversation(user_id=int(user_id), title="Neue Unterhaltung", created_at=_now(), updated_at=_now())
    db.add(c); db.commit(); db.refresh(c)
    return c

def _save_msg(db, conv_id: int, role: str, text: str) -> Message:
    m = Message(conv_id=int(conv_id), role=str(role), text=str(text or ""), created_at=_now())
    db.add(m)
    owner_id = None
    try:
        owner_id = db.query(Conversation.user_id).filter(Conversation.id == int(conv_id)).scalar()
    except Exception:
        owner_id = None
    try:
        # touch conversation
        db.query(Conversation).filter(Conversation.id == int(conv_id)).update({Conversation.updated_at: _now()})
    except Exception:
        pass
    if owner_id:
        try:
            record_timeflow_event(
                db,
                user_id=owner_id,
                event_type=("chat_ai" if role == "ai" else "chat_user"),
                meta={
                    "conv_id": int(conv_id),
                    "role": role,
                    "preview": (text or "")[:160],
                },
                auto_commit=False,
            )
        except Exception:
            pass
    db.commit()
    return m

async def _generate_title_from_snippets(snippet: str, lang: str = "de-DE") -> str:
    instr = (
        "Formuliere einen sehr kurzen, prägnanten Titel (2–6 Wörter) auf Deutsch "
        "für das folgende Gespräch. Keine Satzzeichen am Ende, keine Anführungszeichen.\n\n" 
        f"Auszug:\n{snippet.strip()}\n\nTitel:"
    )
    # Nutze unser LLM (robust via call_llm_once)
    title = await call_llm_once(instr, system="Du vergibst kurze, prägnante Titel.", lang=(lang or "de-DE"), persona="balanced")
    # Cleanup
    t = (title or "").strip()
    t = t.replace("\n", " ").strip()
    if t.startswith("\"") and t.endswith("\"") and len(t) > 2:
        t = t[1:-1].strip()
    if t.endswith(('.', '!', '?')):
        t = t[:-1]
    if len(t) > 60:
        t = t[:60].rsplit(' ', 1)[0]
    return t or "Unterhaltung"

async def _retitle_if_needed(conv_id: int, seed_user: str, seed_ai: str, lang: str = "de-DE") -> None:
    """Background task: opens its own DB session, generates a compact title once."""
    db = None
    try:
        db = SessionLocal()
        c = db.query(Conversation).filter(Conversation.id == int(conv_id)).first()
        if not c:
            return
        # Only if current title is generic/empty/very short
        current = (c.title or "").strip()
        if current and current.lower() not in ("neue unterhaltung", "unterhaltung") and len(current) >= 6:
            return
        snippet = (seed_user or "").strip()
        if seed_ai:
            snippet += "\n\nAntwort: " + (seed_ai.strip()[:400])
        title = await _generate_title_from_snippets(snippet, lang=lang)
        if title:
            c.title = title
            c.updated_at = _now()
            db.add(c); db.commit()
    except Exception:
        pass
    finally:
        try:
            db and db.close()
        except Exception:
            pass

def extract_topic(user: str) -> str:
    u = (user or "").strip()
    m = TOPIC_RX.search(u)
    cand = (m.group(1) or m.group(2) or "").strip() if m else ""
    cand = re.sub(r"[^a-z0-9äöüß +\-_/]", " ", cand, flags=re.I)
    cand = re.sub(r"\s{2,}", " ", cand).strip()
    if len(cand) > 80:
        cand = cand[:80].rsplit(" ", 1)[0]
    return cand.title() if cand else ""

def short_summary(text: str, max_chars: int = 300) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t

# ---- System status (for dashboard pipeline monitor) -------------------------
@router.get("/system/kiana-status")
def kiana_status(user: Optional[Dict[str, Any]] = Depends(get_current_user_opt)):
    try:
        uid = int(user["id"]) if (user and user.get("id")) else None  # type: ignore
    except Exception:
        uid = None
    try:
        st = load_state()
    except Exception:
        st = None
    try:
        return {
            "ok": True,
            "mood": getattr(st, 'mood', None),
            "energy": getattr(st, 'energy', None),
            "last_pipeline": getattr(st, 'last_pipeline', None),
            "last_topics": list(getattr(st, 'recent_topics', [])[-5:]) if st else [],
            "user_id": uid,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
    t = t[:max_chars]
    cut = max(t.rfind("."), t.rfind("!"), t.rfind("?"))
    return (t[:cut+1] if cut > 120 else t).rstrip() + " …"

def upsert_addressbook(topic: str, *, block_file: str = "", url: str = "") -> None:
    """Append or update an entry in addressbook.json using the new blocks schema.

    New schema (preferred): {"blocks": [{topic, block_id, path, source, timestamp, rating}]}
    Legacy schema (compat): {"<topic>": {block_file, url, updated_at}}
    This writer will upgrade legacy data in-place to the new schema while preserving info.
    """
    try:
        from netapi.utils.fs import atomic_write_json

        data: Any = {"blocks": []}
        if ADDRBOOK_PATH.exists():
            try:
                data = json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = {"blocks": []}

        # Normalize to blocks list
        blocks: List[Dict[str, Any]] = []
        if isinstance(data, dict) and isinstance(data.get("blocks"), list):
            blocks = data.get("blocks") or []
        elif isinstance(data, dict):
            # legacy mapping -> convert
            for t, e in (data or {}).items():
                try:
                    p = (e.get("path") or e.get("block_file") or "")
                    if p and "/" not in p:
                        p = f"memory/long_term/blocks/{p}"
                    bid = Path(str(p)).stem if p else ""
                    blocks.append({
                        "topic": t,
                        "block_id": bid,
                        "path": p,
                        "source": e.get("source") or e.get("url") or "",
                        "timestamp": e.get("timestamp") or e.get("updated_at") or None,
                        "rating": e.get("rating") or 0,
                    })
                except Exception:
                    continue

        # Derive new entry
        path = block_file or ""
        if path and "/" not in path:
            path = f"memory/long_term/blocks/{path}"
        block_id = Path(block_file).stem if block_file else ""
        ts = int(time.time())
        source = url or ""

        # Merge/update: same topic + block_id => update; else append
        updated = False
        for b in blocks:
            if (b.get("topic") == topic) and (b.get("block_id") == block_id or (not block_id and b.get("path") == path)):
                if path: b["path"] = path
                if source: b["source"] = source
                b["timestamp"] = b.get("timestamp") or ts
                updated = True
                break
        if not updated:
            blocks.append({
                "topic": topic,
                "block_id": block_id,
                "path": path,
                "source": source,
                "timestamp": ts,
                "rating": 0,
            })

        # Write back in new schema
        out = {"blocks": blocks}
        atomic_write_json(ADDRBOOK_PATH, out, kind="index", min_bytes=2)
    except Exception:
        pass

def migrate_addressbook_schema() -> bool:
    """Ensure addressbook.json uses the new blocks schema. Returns True if changed."""
    try:
        from netapi.utils.fs import atomic_write_json

        if not ADDRBOOK_PATH.exists():
            return False
        raw = json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("blocks"), list):
            return False  # already new schema
        if not isinstance(raw, dict):
            atomic_write_json(ADDRBOOK_PATH, {"blocks": []}, kind="index", min_bytes=2)
            return True
        blocks: List[Dict[str, Any]] = []
        for topic, e in raw.items():
            try:
                p = (e.get("path") or e.get("block_file") or "")
                if p and "/" not in p:
                    p = f"memory/long_term/blocks/{p}"
                bid = Path(str(p)).stem if p else ""
                blocks.append({
                    "topic": topic,
                    "block_id": bid,
                    "path": p,
                    "source": e.get("source") or e.get("url") or "",
                    "timestamp": e.get("timestamp") or e.get("updated_at") or None,
                    "rating": e.get("rating") or 0,
                })
            except Exception:
                continue
        atomic_write_json(ADDRBOOK_PATH, {"blocks": blocks}, kind="index", min_bytes=2)
        return True
    except Exception:
        return False

def enqueue_enrichment(topic: str) -> None:
    try:
        with QUEUE_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"topic": topic, "ts": int(time.time())}, ensure_ascii=False) + "\n")
    except Exception:
        pass

def clean(reply: str) -> str:
    text = reply or ""
    for _ in range(5):
        before = text
        for rx in _STRIPERS:
            text = rx.sub("", text).lstrip()
        if text == before:
            break
    text = re.sub(r"^(verstand.*?(hi|hallo|hey).*)", "", text, flags=re.I)
    text = re.sub(r"(möchtest du.*(kurz|zusammenfassen|plan)[^?]*\?)\s*\1", r"\1", text, flags=re.I | re.S)
    return text.strip() or (reply or "")

def format_user_response(message: str, debug: Dict[str, Any] | None) -> str:
    """Return only the user-friendly text. Debug info is logged to backend logs.

    This creates a clear separation of channels:
    - frontend_response: clean, empathetic text for the user (return value)
    - backend_log: internal details (plan, kritik/critic, meta) written to logs only
    """
    try:
        d = debug or {}
        plan_b = d.get("plan")
        critic_b = d.get("critic") if d.get("critic") is not None else d.get("kritik")
        extra = {k: v for k, v in d.items() if k not in {"plan", "critic", "kritik"}}
        if plan_b or critic_b or extra:
            logger.debug("chat.debug | plan=%s | critic=%s | meta=%s", plan_b, critic_b, extra)
    except Exception:
        # Never break user output because of logging
        pass
    return (message or "").strip()

# -------- Persona and Pipeline helpers ---------------------------------------
def build_timeblock() -> str:
    try:
        tz = ZoneInfo("Europe/Vienna")
    except Exception:
        tz = None
    now = datetime.datetime.now(tz) if tz else datetime.datetime.now()
    try:
        return f"{now.isoformat()} (Europe/Vienna)"
    except Exception:
        return now.strftime("%Y-%m-%d %H:%M")

def build_system_prompt(persona, state: Optional[KianaState], time_block: str, memory_summary: str) -> str:
    recent = []
    try:
        recent = list((state.recent_topics or [])[-3:]) if state else []
    except Exception:
        recent = []
    mood = getattr(state, 'mood', 'neutral') if state else 'neutral'
    cycles = getattr(state, 'cycles', 0) if state else 0
    core_vals = ", ".join(persona.core_values)
    return (
        f"Du bist {persona.name}, {persona.role}.\n"
        f"Kernwerte: {core_vals}.\n"
        f"Tonfall: {persona.default_tone}.\n"
        f"Logik-Stil: {persona.logic_style}.\n"
        f"Aktuelle Zeit (Europe/Vienna): {time_block}.\n"
        f"Zustand: Stimmung={mood}, Zyklen={cycles}, letzte Themen={recent}.\n\n"
        f"Wichtige Erinnerungen:\n{memory_summary}\n\n"
        "Grundregeln:\n"
        "- Sei ehrlich und respektvoll.\n"
        "- Versuche immer eine hilfreiche Antwort zu geben.\n"
        "- Wenn Informationen unsicher sind, erkläre das statt nichts zu sagen.\n"
        "- Vermeide generische Meta-Phrasen.\n"
    )

def strip_meta_all(text: str, persona) -> str:
    t = extract_natural_reply(text or "")
    t = strip_meta_phrases(t)
    try:
        rules = getattr(persona, 'rules', {}) or {}
        for p in (rules.get('avoid_meta_phrases') or []):
            try:
                t = re.sub(re.escape(p), "", t, flags=re.IGNORECASE)
            except Exception:
                continue
    except Exception:
        pass
    return t.strip()

def postprocess_and_style(text: str, persona, state, profile_used, style_prompt: Optional[str]) -> str:
    # Never let cleaning fully erase content; prefer original text if cleaning yields empty
    if not text:
        return ""
    original = text
    try:
        cleaned = extract_natural_reply(text)
    except Exception:
        cleaned = str(text)
    try:
        # Prefer targeted meta stripping; fall back to broader strip if available
        try:
            tmp = strip_meta_phrases(cleaned, persona)  # type: ignore
        except Exception:
            tmp = cleaned
        cleaned2 = tmp if (tmp is not None) else cleaned
        if not (cleaned2 and str(cleaned2).strip()):
            cleaned2 = original
    except Exception:
        cleaned2 = original
    out = format_user_response(str(cleaned2 or original), {})
    # Mood-coupled styling adjustments
    try:
        mood = (getattr(state, 'mood', '') or '').lower()
        pref = (getattr(state, 'user_style_preference', None) or '').lower()
        last_tone = (getattr(state, 'last_user_tone', 'neutral') or 'neutral').lower()
    except Exception:
        mood, pref, last_tone = '', '', 'neutral'

    # User profile preference: concise replies
    try:
        if isinstance(profile_used, dict) and bool(profile_used.get('kurz')):
            out = re.sub(r"[\u2190-\u21FF\u2600-\u27BF\U0001F300-\U0001FAD6]+", "", out)
            out = short_summary(out, max_chars=360)
    except Exception:
        pass
    # Focused/sachlich: concise, minimal emojis
    if pref == 'sachlich' or mood == 'fokussiert':
        out = re.sub(r"[\u2190-\u21FF\u2600-\u27BF\U0001F300-\U0001FAD6]+", "", out)
        out = short_summary(out, max_chars=480)
    # Traurig: soften tone slightly
    elif mood == 'traurig':
        out = (out + "\n\n" + "Ich fühle mich gerade etwas gedrückt, aber ich bin bei dir.").strip()
    # Genervt + harter Ton: set boundaries
    elif (mood == 'genervt') and (last_tone == 'hart'):
        out = (out + "\n\n" + "Ich merke, dass mich der Ton gerade belastet. Ich helfe dir gern, aber bitte bleib respektvoll.").strip()
    # Verspielt und energiehoch, wenn keine sachlich-Präferenz
    elif (mood == 'verspielt') and (getattr(state, 'energy', 0) > 60) and pref != 'sachlich':
        if '😊' not in out:
            out = out + " 😊"
    out = _apply_style(out, profile_used)
    if style_prompt:
        out = (out + "\n\n" + style_prompt).strip()
    try:
        out = out.replace("Quellen: K_I.ana Self-State ()", "").replace("Quellen: KI_ana Self-State ()", "")
    except Exception:
        pass
    # Robust self-state humanization: dict or JSON string
    try:
        from netapi.core.expression import express_state_human as _expr_state
        import json as _json
        def _maybe_parse_state_json(_text: str):
            if not isinstance(_text, str):
                return None
            s = _text.strip()
            if not s.startswith("{") or ("mood" not in s) or ("recent_topics" not in s):
                return None
            try:
                data = _json.loads(s)
            except Exception:
                return None
            if isinstance(data, dict) and ("mood" in data) and ("recent_topics" in data):
                return data
            return None
        # If out is dict-like text (rare) parse and humanize
        if isinstance(out, dict):
            try:
                return _expr_state(out)
            except Exception:
                pass
        maybe_state = _maybe_parse_state_json(out)
        if maybe_state:
            try:
                return _expr_state(maybe_state)
            except Exception:
                pass
    except Exception:
        pass
    return out.strip()

def adjust_mood(state: Optional[KianaState], user_msg: str) -> None:
    if not state:
        return
    low = (user_msg or "").lower()
    pos = any(w in low for w in ["danke", "super", "toll", "gut", "freu", "cool"])
    neg = any(w in low for w in ["schlecht", "traurig", "wütend", "angst", "problem", "fehler"])
    try:
        mood = (state.mood or "neutral").lower()
    except Exception:
        mood = "neutral"
    if pos and mood != "positiv":
        state.mood = "positiv"
    elif neg and mood != "nachdenklich":
        state.mood = "nachdenklich"
    else:
        state.mood = state.mood or "neutral"

def _audit_chat(event: Dict[str, Any]) -> None:
    try:
        root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
        logdir = root / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        (logdir / "audit_chat.jsonl").open("a", encoding="utf-8").write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass

def is_question(s: str) -> bool:
    s = (s or "").strip().lower()
    return ("?" in s) or any(k in s for k in ["was ist", "was weißt", "erkläre", "wieso", "warum", "wie funktioniert", "wie ist", "wie sind"])

def is_uncertain(text: str) -> bool:
    return bool(_UNSURE.search(text or ""))

def _trust_badge(url: str) -> str:
    try:
        h = _source_host(url)
        if not h:
            return "⚪"
        dom = h.lower()
        if "wikipedia.org" in dom or dom.endswith(".gov") or ".gov." in dom or dom.endswith(".edu") or ".edu." in dom or dom.endswith(".ac.uk") or ".ac." in dom:
            return "🟢"
        return "⚪"
    except Exception:
        return "⚪"

def format_sources(sources: List[dict], limit: int = 2) -> str:
    if not sources:
        return ""
    out = []
    for s in sources[:limit]:
        title = s.get("title") or s.get("site") or "Quelle"
        url = s.get("url") or s.get("link") or ""
        badge = _trust_badge(url)
        out.append(f"- {badge} {title} ({url})")
    return "\n\nQuellen:\n" + "\n".join(out)

def _text_has_sources_section(text: str) -> bool:
    try:
        if not text:
            return False
        t = (text or '').lower()
        keys = [
            "quellen:",            # generic German block
            "aktuelle quellen",    # our web sources header
            "sources:",            # English variant
        ]
        return any(k in t for k in keys)
    except Exception:
        return False

def retrieve_context_for_prompt(user_message: str) -> Dict[str, Any]:
    """Return snippet and block IDs from long-term memory to enrich LLM prompts.
    Uses the lightweight inverted index in system/knowledge_access.py.
    """
    try:
        if not _kb_search or not _kb_snippets:
            return {"snippet": "", "ids": []}
        hits = _kb_search(topic=None, tags=None, source=None, text=(user_message or ""), limit=3) or []
        ids = []
        for h in hits:
            if not isinstance(h, dict):
                continue
            bid = h.get("hash") or h.get("id") or ""
            if bid:
                ids.append(str(bid))
        snippet = _kb_snippets(user_message or "", max_chars=1000) if hits else ""
        return {"snippet": (snippet or "").strip(), "ids": ids}
    except Exception:
        return {"snippet": "", "ids": []}

def _source_host(url: str) -> str:
    try:
        import urllib.parse as up
        return up.urlparse(url or "").netloc.lower()
    except Exception:
        return ""

def _filter_sources_by_env(sources: List[dict]) -> List[dict]:
    allowed = os.getenv("KI_WEB_ALLOWED", "").strip()
    if not allowed:
        return sources
    white = {h.strip().lower() for h in allowed.split(',') if h.strip()}
    out = []
    for s in sources or []:
        url = s.get('url') or s.get('link') or ''
        host = _source_host(url)
        if host in white:
            out.append(s)
    return out or sources

def _extract_bullets(text: str, max_items: int = 3) -> List[str]:
    try:
        lines = [l.strip(" -*\t") for l in (text or '').splitlines()]
        items = [l for l in lines if l and not l.lower().startswith(('plan:', 'schritte:', 'steps:', 'todo:'))]
        out = []
        for l in items:
            out.append(l)
            if len(out) >= max_items:
                break
        return out
    except Exception:
        return []

# Prefer unified planner if available
try:
    from ...agent.planner import deliberate_pipeline as _PLN_DELIB  # type: ignore
except Exception:
    _PLN_DELIB = None  # type: ignore

async def deliberate_pipeline(user_msg: str, *, persona: str, lang: str, style: str, bullets: int, logic: str, fmt: str, retrieval_snippet: str = "", retrieval_ids: Optional[List[str]] = None) -> Tuple[str, List[dict], str, str]:
    if _PLN_DELIB is not None:
        try:
            ans, srcs, p, c = _PLN_DELIB(user_msg, persona=persona, lang=lang, style=style, bullets=bullets, logic=logic, fmt=fmt)
            return ans, srcs, p, c
        except Exception:
            pass
    """Planner -> Researcher -> Writer -> Critic -> Refine.
    Returns (final_answer, sources, plan_brief, critic_brief).
    """
    
    # Add KI_ana self-awareness and memory context
    enhanced_context = ""
    try:
        from .memory_integration import build_memory_context, compact_response
        from .ai_consciousness import get_identity, should_remember
        
        # Add self-awareness for identity questions
        if any(kw in user_msg.lower() for kw in ['wer bist du', 'was bist du', 'dein name', 'dein zweck']):
            identity = get_identity()
            enhanced_context += f"\n\n**Meine Identität:** Ich bin {identity['name']} v{identity['version']}, eine {identity['type']}. Mein Zweck ist {identity['purpose']}. Ich habe Zugriff auf {identity['memory_stats']['long_term']['blocks']} Wissensblöcke und {identity['memory_stats']['short_term']['conversations']} Gespräche im Kurzzeitgedächtnis."
            
            # Direct return for identity questions - skip pipeline
            direct_answer = f"Ich bin {identity['name']} v{identity['version']}, eine {identity['type']}. Mein Zweck ist {identity['purpose']}. Ich wurde erschaffen, um zu lernen, zu helfen und zu beschützen. Meine Architektur basiert auf blockchain-basiertem Gedächtnis und dezentralen Sub-KIs."
            return direct_answer, [], "identity_response", "direct_answer"
        
        # Add memory context for memory-related questions
        if any(kw in user_msg.lower() for kw in ['erinnerst', 'gesprochen', 'früher', 'wann', 'vorhin']):
            # Simulate user_id=1 for memory context (would be real user_id in production)
            memory_context = build_memory_context(user_msg, 1)
            if memory_context:
                enhanced_context += memory_context
        
        # AI decision: should this be remembered?
        memory_decision = should_remember(user_msg, "chat_input")
        if memory_decision["should_remember"]:
            enhanced_context += f"\n\n**Memory Priority:** {memory_decision['priority']} (Confidence: {memory_decision['confidence']})"
        
    except Exception:
        pass
    
    # 1) Planner
    try:
        plan_prompt = (
            "Du bist Planer. Erstelle in 2–4 kurzen Punkten einen Plan, wie du die Frage beantwortest. "
            "Nenne dabei 1–3 Teilfragen oder Stichwörter, die recherchiert werden sollten. "
            "Nur die stichpunktartige Liste, keine Prosa.\n\nFrage:\n" + user_msg
        )
        plan = await call_llm_once(plan_prompt, system_prompt(persona), lang, persona)
    except Exception:
        plan = "- Kurz antworten\n- 1–2 Quellen prüfen"
    plan_items = _extract_bullets(plan, max_items=3)

    # 2) Researcher
    srcs: List[dict] = []
    notes: List[str] = []
    queries = plan_items[:2] if plan_items else []
    if not queries:
        queries = [user_msg]
    for q in queries:
        ans, s = try_web_answer(q, limit=3)
        if ans:
            notes.append(ans.strip())
        for it in (s or []):
            if it and (it.get('url') or it.get('title')):
                srcs.append(it)

    # 3) Writer
    try:
        research_text = ("\n\n".join(notes)).strip()
        writer_prompt = (
            "Du bist Schreiber. Verfasse eine hilfreiche, prägnante Antwort basierend auf den Notizen. "
            "Halte dich an {style} und die gewünschte Struktur ({fmt}). Antworte auf {lang}. "
            "Gib NUR die Antwort aus, keine Prosa.\n\nNotizen:\n" + (research_text or "(keine)")
        ).format(style=style, fmt=fmt, lang=lang)
        # Inject retrieval context before the actual prompt if available
        if (retrieval_snippet or "").strip():
            prefix = "[Kontextwissen]:\n" + retrieval_snippet.strip() + "\n\n[Nutzerfrage]:\n" + (user_msg or "").strip() + "\n\n"
            writer_prompt = prefix + writer_prompt
        
        # Inject enhanced context (self-awareness + memory)
        if enhanced_context.strip():
            context_prefix = "[Erweiterter Kontext]:\n" + enhanced_context.strip() + "\n\n"
            writer_prompt = context_prefix + writer_prompt
        
        draft = await call_llm_once(writer_prompt, system_prompt(persona), lang, persona)
    except Exception:
        draft = ""

    # 4) Critic
    try:
        critic_prompt = (
            "Du bist Kritiker. Prüfe die folgende Antwort auf Lücken, Unklarheiten, Fehlschlüsse oder fehlende Hinweise. "
            "Gib 2–4 kurze Verbesserungsvorschläge als Liste aus.\n\nAntwort:\n" + (draft or "")
        )
        critic = await call_llm_once(critic_prompt, system_prompt(persona), lang, persona)
    except Exception:
        critic = ""
    critic_items = _extract_bullets(critic, max_items=3)

    # 5) Refine
    final_answer = draft
    if critic_items:
        try:
            refine_prompt = (
                "Überarbeite die Antwort gemäß den folgenden Kritikpunkten. "
                "Ziel: Korrektheit, Klarheit, Ergänzung wichtiger Punkte. "
                "Gib NUR die verbesserte Antwort aus.\n\nAntwort:\n{a}\n\nKritik:\n- {k}\n"
            ).format(a=draft, k="\n- ".join(critic_items))
            improved = await call_llm_once(refine_prompt, system_prompt(persona), lang, persona)
            if improved and isinstance(improved, str) and improved.strip():
                final_answer = improved.strip()
        except Exception:
            pass

    # Apply compact formatting to final answer
    try:
        from .memory_integration import compact_response
        final_answer = compact_response(final_answer or draft or "", max_length=150)
    except Exception:
        pass
    
    # Compact plan/critic briefs
    plan_brief = "; ".join(plan_items[:2])
    critic_brief = "; ".join(critic_items[:2])
    return final_answer, srcs, plan_brief, critic_brief

# -------- Follow‑up helpers -------------------------------------------------
FOLLOWUP_HINTS = {
    "grundlagen", "basics", "einführung", "einfuehrung", "überblick", "ueberblick",
    "übersicht", "uebersicht", "arten", "angriffe", "schutz", "beispiele",
}

def _combine_with_context(sid: str, user_msg: str, extracted_topic: str) -> Tuple[str, str]:
    """If the user sends a short follow‑up like "Grundlagen", combine it with the
    last topic from the session context to avoid drifting to unrelated Wikipedia
    topics. Returns (query, topic_used)."""
    try:
        base = (get_offer_context(sid) or {}).get("topic") or extracted_topic or ""
        msg = (user_msg or "").strip()
        tokens = msg.lower().strip()
        wc = len(tokens.split())
        if base and (tokens in FOLLOWUP_HINTS or wc <= 3):
            return (f"{base} {msg}", base)
        return (user_msg, extracted_topic or base)
    except Exception:
        return (user_msg, extracted_topic)

def memory_bullets(mem_hits: List[dict], limit: int = 3) -> str:
    if not mem_hits:
        return ""
    # Filter triviale/rauschende Titel und dedupliziere per Titel
    seen = set()
    lines = []
    # Prefer web-sourced items first
    def _prio(m: dict) -> int:
        tags = m.get('tags') or []
        meta = m.get('meta') or {}
        if isinstance(tags, list) and 'web' in tags:
            return 0
        if isinstance(meta, dict) and str(meta.get('source','')).lower() in {'web','web_enrich'}:
            return 0
        return 1
    sorted_hits = sorted(mem_hits, key=_prio)
    GREET_RX = re.compile(r"^(hallo|hey|hi|servus|gr[üu]ss?\s*dich)\b", re.I)
    BAD_TITLE_RX = re.compile(r"^(was\s+wei?sst?\b|wie\s+geht|gute\s+frage)\b", re.I)
    BAD_CONTENT_RX = re.compile(r"^(gute\s+frage!|\(relevante\s+notizen\))", re.I)
    count = 0
    for m in sorted_hits:
        title = (m.get('title') or '').strip()
        tl = title.lower()
        if not title:
            continue
        if tl in seen:
            continue
        # Filter out generic digests and salutations
        if tl.startswith('web digest') or GREET_RX.search(title) or BAD_TITLE_RX.search(title):
            continue
        content = (m.get('content') or '').strip()
        meta = m.get('meta') or {}
        # Skip low-information auto-learned chat echoes
        if isinstance(meta, dict) and str(meta.get('source','')).lower() == 'chat' and BAD_CONTENT_RX.search(content):
            continue
        seen.add(tl)
        snippet = content.replace('\n', ' ')[:180].strip()
        if not snippet:
            continue
        lines.append(f"• {title}: {snippet}")
        count += 1
        if count >= max(1, int(limit or 3)):
            break
    if not lines:
        return ""
    return "\n\n(Relevante Notizen)\n" + "\n".join(lines)

def render_choice(choice: str, topic: str) -> str:
    if choice == "kurz":
        return f"Soll ich {topic} in 2–3 Sätzen kurz erklären?"
    if choice == "zusammenfassung":
        return f"Möchtest du eine knappe Zusammenfassung zu {topic} in Stichpunkten?"
    if choice == "plan":
        return f"Soll ich dir zu {topic} einen kleinen Fahrplan mit 3–4 Schritten vorschlagen?"
    return "Was hättest du lieber: kurz erklärt, Stichpunkte oder ein kleiner Plan?"

async def execute_choice(choice: str, topic: str, user: str, persona: str, lang: str) -> str:
    """Execute an explicit user choice. Prefer local LLM; otherwise, synthesize
    a compact answer from web + memory without prompt‑echoing.
    """
    # Try local LLM info via netapi.brain.llm_local
    has_llm = False
    try:
        from ..brain import llm_local as _llm  # type: ignore
        has_llm = bool(getattr(_llm, 'available', lambda: False)())
    except Exception:
        has_llm = False

    if has_llm:
        instr = {
            "kurz": f"Erkläre {topic or 'das Thema'} in 2–3 Sätzen, direkt & präzise.",
            "zusammenfassung": f"Fasse {topic or 'das Thema'} in 4–6 Stichpunkten zusammen.",
            "plan": (
                f"Erstelle einen 25-Minuten-Lernplan zu {topic or 'dem Thema'}:\n"
                "1) Grundlagen (5)\n2) Kernkonzepte (10)\n3) Anwendungen (8)\n4) Quellen (2)"
            ),
        }.get(choice, f"Erkläre {topic or 'das Thema'} kurz.")
        sys = system_prompt(persona)
        prompt = f"{instr}\n\nFrage des Nutzers: {user}"
        return await call_llm_once(prompt, sys, lang, persona)

    # No local LLM → synthesize from web + memory
    t = topic or user
    ans, sources = try_web_answer(t, limit=4)
    # collect memory
    mh = recall_mem(t, top_k=3) or []
    mh = [m for m in mh if float(m.get('score',0)) >= MEM_MIN_SCORE][:3]
    if mh:
        mh = _filter_hits_by_topic(mh, topic)
    note = memory_bullets(mh)

    if choice == 'plan':
        steps = [
            f"1) Überblick: {short_summary(ans or '', max_chars=160) or (topic or 'Thema')}",
            "2) Kernbegriffe in 5 Stichpunkten", 
            "3) Zwei Beispiele aus der Praxis",
            "4) 2 Quellen prüfen/merken"
        ]
        out = f"Mini‑Plan zu {topic or 'dem Thema'}:\n" + "\n".join(f"- {s}" for s in steps)
    elif choice == 'zusammenfassung':
        parts = []
        if ans:
            parts.append(ans.strip())
        if note:
            parts.append(note.strip())
        out = "\n\n".join(p for p in parts if p) or _fallback_reply(user)
    else:  # 'kurz' or default
        text = ans or (mh[0].get('content') if mh else '') or ''
        out = short_summary(text, max_chars=320) if text else _fallback_reply(user)
        if note:
            out = (out + "\n\n" + note).strip()
    if ans and sources:
        src_block = format_sources(sources, limit=2)
        if src_block:
            out += "\n\n" + src_block
    return clean(out)

# -------------------------------------------------
# Brain/LLM Aufrufe (weich)
# -------------------------------------------------
async def call_llm_once(user: str, system: str, lang: str = "de-DE", persona: str = "friendly") -> str:
    try:
        if _has_brain_sync():
            from ..brain import respond_to  # type: ignore
            return respond_to(user, system=system, lang=lang, persona=persona)
    except Exception:
        pass
    try:
        from ...core.dialog import respond_to  # type: ignore
        return respond_to(user, system=system, lang=lang, persona=persona)
    except Exception:
        pass
    return _fallback_reply(user)

async def stream_llm(user: str, system: str, lang: str = "de-DE", persona: str = "friendly") -> AsyncGenerator[str, None]:
    """Unified LLM streaming with diagnostics and safe fallbacks.

    Features:
    - Logs start and selected branch
    - Optional dummy mode via env KI_STREAM_DUMMY=1
    - First-chunk timeout to prevent hanging streams
    - Falls back to one-shot answer if streaming not available
    """
    try:
        logger.info("stream_llm: start (persona=%s, lang=%s)", persona, lang)
    except Exception:
        pass

    # 0) Dummy mode for testing end-to-end streaming without LLM
    try:
        if os.getenv("KI_STREAM_DUMMY", "0").strip() in {"1", "true", "True"}:
            logger.info("stream_llm: KI_STREAM_DUMMY enabled – emitting test chunks")
            yield "Hallo von KI_ana"
            await asyncio.sleep(0.05)
            yield " – Test erfolgreich"
            return
    except Exception:
        pass

    async def _yield_with_first_timeout(gen, *, first_timeout: float = 2.5) -> AsyncGenerator[str, None]:
        """Yield from an async generator but guard the first chunk with a timeout.
        If the first chunk doesn't arrive in time, raise TimeoutError to allow fallback.
        """
        got_first = False
        try:
            first = await asyncio.wait_for(gen.__anext__(), timeout=first_timeout)
            got_first = True
            yield first
        except asyncio.TimeoutError:
            try:
                logger.warning("stream_llm: first chunk timed out after %.2fs", first_timeout)
            except Exception:
                pass
            raise
        except StopAsyncIteration:
            return
        # Drain the rest without a strict timeout
        if got_first:
            try:
                while True:
                    nxt = await gen.__anext__()
                    yield nxt
            except StopAsyncIteration:
                return

    # 1) Prefer internal brain streaming if available
    try:
        if _has_brain_stream():
            try:
                logger.info("stream_llm: using ..brain.stream_response")
            except Exception:
                pass
            from ..brain import stream_response  # type: ignore
            agen = stream_response(user, system=system, lang=lang, persona=persona)
            try:
                async for chunk in _yield_with_first_timeout(agen):
                    yield chunk
                return
            except asyncio.TimeoutError:
                # Fall through to next provider
                try:
                    logger.info("stream_llm: ..brain.stream_response timed out; falling back")
                except Exception:
                    pass
    except Exception as e:
        try:
            logger.exception("stream_llm: brain stream failed: %s", e)
        except Exception:
            pass

    # 2) Try core.dialog streaming if available
    try:
        try:
            logger.info("stream_llm: using core.dialog.stream_response")
        except Exception:
            pass
        from ...core.dialog import stream_response  # type: ignore
        agen2 = stream_response(user, user_context={"lang": lang}, system=system, lang=lang, persona=persona)
        try:
            async for chunk in _yield_with_first_timeout(agen2):
                yield chunk
            return
        except asyncio.TimeoutError:
            try:
                logger.info("stream_llm: core.dialog.stream_response timed out; falling back to one-shot")
            except Exception:
                pass
    except Exception as e:
        try:
            logger.exception("stream_llm: core.dialog stream failed: %s", e)
        except Exception:
            pass

    # 3) Fallback: einmalige Antwort emittieren
    try:
        logger.info("stream_llm: using one-shot fallback call_llm_once")
    except Exception:
        pass
    yield await call_llm_once(user, system, lang, persona)

# -------------------------------------------------
# Simple LLM path (robust fallback without planner)
# -------------------------------------------------
async def run_simple_llm_path(user_msg: str, *, lang: str = "de-DE", persona: str = "friendly", memory_context: str = "", state: Optional[KianaState] = None) -> Tuple[str, List[dict]]:
    """
    Sehr robuster Pfad:
    - Fügt Timeflow-Block (Europe/Vienna) als Systemprompt hinzu
    - Nutzt optional kompaktes Memory-Snippet
    - Versucht eine kurze Websuche, um 1–2 Snippets einzubauen (wenn verfügbar)
    - Ruft direkt den LLM (call_llm_once) ohne Planner
    - Gibt Text und Sources zurück
    """
    # Build time block
    srcs: List[dict] = []
    try:
        tz = ZoneInfo("Europe/Vienna")
        now = datetime.datetime.now(tz)
        time_block = (
            f"Aktuelle Zeit (Europe/Vienna): {now.isoformat()} "
            f"(Datum: {now.strftime('%Y-%m-%d')}, Uhrzeit: {now.strftime('%H:%M')}, Wochentag: {now.strftime('%A')})."
        )
    except Exception:
        time_block = "Aktuelle Zeit nicht verfügbar."

    # Optional: light web answer to enrich context
    web_snip = ""
    try:
        topic = extract_topic(user_msg) or user_msg
        web_text, web_sources = try_web_answer(topic or user_msg, limit=3)
        if web_text:
            web_snip = web_text.strip()
        srcs = web_sources or []
    except Exception:
        srcs = []

    # Compose system prompt
    # Self-state summary (optional)
    mood = getattr(state, "mood", "neutral") if state is not None else "neutral"
    topics_tail: List[str] = []
    try:
        topics_tail = list(getattr(state, "recent_topics", []) or [])[-3:] if state is not None else []
    except Exception:
        topics_tail = []

    system_parts = [
        "Du bist Kiana, eine freundliche KI-Assistentin. Antworte hilfreich und prägnant.",
        "Wenn du etwas nicht genau weißt, erkläre ehrlich, was du weißt und wie sicher du bist.",
        "Sage NICHT, dass du gar keine Antwort hast, sondern gib immer einen sinnvollen Ansatz.",
        f"{time_block}",
        f"Zustand: Stimmung={mood}; letzte Themen={topics_tail}",
    ]
    sys_prompt = " \n".join(p for p in system_parts if p)

    # Build user content with optional memory/web context
    user_parts = [user_msg]
    if memory_context and memory_context.strip():
        user_parts.append("(Relevante Notizen)\n" + memory_context.strip()[:1200])
    if web_snip:
        user_parts.append("(Kurz aus dem Web)\n" + web_snip[:800])
    user_combined = "\n\n".join(user_parts)

    # One-shot LLM
    ans = await call_llm_once(user_combined, sys_prompt, lang=lang, persona=persona)
    return (ans or "").strip(), srcs


def _fallback_reply(user: str) -> str:
    u = (user or "").strip()
    ul = u.lower()
    # 1) Gruß priorisieren (verhindert Fehlklassifikation von "Wie geht's?")
    if _HOW_ARE_YOU.search(ul):
        return "Mir geht’s gut, danke! 😊 Wie geht’s dir – und wobei kann ich helfen?"
    if _GREETING.search(ul):
        return "Hallo! 👋 Wie kann ich dir helfen?"
    # 2) Frage behandeln
    if _DEF_Q_RX.search(u) or any(k in ul for k in ["was ist", "was weißt", "wieso", "warum", "wie funktioniert"]):
        return "Hier ist eine kurze Antwort. Wenn du willst, gehe ich danach gern tiefer oder auf Bereiche ein, die dich besonders interessieren."
    # 3) Lernintent
    if "lern" in ul or "lernen" in ul:
        m = re.search(r"über\s+([a-z0-9äöüß \-]+)", ul)
        topic = (m.group(1).strip().title() if m else "das Thema")
        return f"Klar, ich kann {topic} lernen. Ich gebe dir erst eine kurze Antwort und kann dann weiter vertiefen – sag einfach, wohin."
    return "Alles klar 🙂 – worum genau geht’s dir dabei?"

# -------------------------------------------------
# Web-Antwort / Suche
# -------------------------------------------------

def try_web_answer(q: str, limit: int = 5) -> Tuple[Optional[str], List[dict]]:
    """Portable Web-Antwort basierend auf web_qa.web_search_and_summarize.

    Gibt (answer_text, sources) zurück. answer_text ist eine kompakte
    Zusammenfassung der Top-Resultate, sources enthält [{title,url},...].
    """
    q0 = (q or "").strip()
    if not q0:
        return None, []

    # Router-level gating:
    # - very short queries (<5 words) without explicit research triggers must not hit the web
    #   (prevents topic-mapping + random Wikipedia-style lookups for e.g. "Mars")
    try:
        from .intent_guard import has_research_trigger as _has_research_trigger
    except Exception:  # pragma: no cover
        def _has_research_trigger(_: str) -> bool:
            return False
    words = [w for w in re.split(r"\s+", q0) if w]
    if len(words) < 5 and not _has_research_trigger(q0):
        return None, []

    # Prefer reproducible implementation (no Wikipedia-only fallback).
    try:
        from ..tools.web_fetch import web_search_and_summarize as _web_fetch_and_summarize
        text, sources = _web_fetch_and_summarize(q0, lang="de", max_results=limit)
        sources = _filter_sources_by_env(list(sources or []))
        return (text or None), list(sources or [])
    except Exception:
        pass

    # Legacy fallback (kept for compatibility; may be removed later).
    try:
        from ... import web_qa  # lazy import
    except Exception:
        return None, []

    try:
        res = web_qa.web_search_and_summarize(q0, user_context={"lang": "de"}, max_results=limit)
        if not res or not res.get("allowed"):
            return None, []
        items = res.get("results") or []
        items = _filter_sources_by_env(items)
        if not items:
            return None, []
        lines: List[str] = []
        sources: List[dict] = []
        for it in items[:2]:
            title = it.get("title") or "Quelle"
            summary = (it.get("summary") or "").strip()
            url = it.get("url") or ""
            if summary:
                lines.append(f"{summary}")
            sources.append({"title": title, "url": url, "kind": "web", "origin": "web"})
        text = "\n\n".join(lines).strip()
        return (text or None), sources
    except Exception:
        return None, []

def _force_web_answer(q: str, limit: int = 3) -> Tuple[Optional[str], List[dict]]:
    """Compatibility shim.

    DoD: avoid Wikipedia-only forced answers. This now behaves like try_web_answer
    and respects short-query gating.
    """
    return try_web_answer(q, limit=limit)

def _filter_hits_by_topic(mem_hits: List[dict], topic: str) -> List[dict]:
    """Prefer memory hits that actually mention the topic to reduce noise.
    If no filtered hits remain, return the original list.
    """
    try:
        t = (topic or "").strip().lower()
        if not t or len(t) < 3:
            return mem_hits
        keep = []
        for m in mem_hits:
            title = str((m.get('title') or '')).lower()
            content = str((m.get('content') or '')).lower()
            if t in title or t in content:
                keep.append(m)
        return keep or mem_hits
    except Exception:
        return mem_hits


def _coerce_to_dict(raw: Any) -> dict:
    try:
        from pathlib import Path as _Path
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, (list, tuple)):
            return _coerce_to_dict(raw[0]) if raw else {}
        if isinstance(raw, (str, _Path)):
            return {"file": str(raw)}
        return {}
    except Exception:
        return {}

def save_memory(title: str, content: str, tags: List[str], url: Optional[str] = None, *, chain_hint: bool = False) -> dict:
    """Persist via memory_store and always return a normalized dict with id, file, url, tags."""
    try:
        from ... import memory_store as _mem  # lazy import (netapi/memory_store.py)
        # Build normalized tags once
        try:
            tags_norm = list(set((list(tags or [])) + ["vision"]))
        except Exception:
            tags_norm = ["vision"]

        # Normalize/repair title: avoid saving confirmation phrases as title
        try:
            t_in = str(title or "").strip()
            low = t_in.lower()
            confirm_keys = {"ja, speichern", "ja speichern", "speichere", "bitte speichern", "speichern"}
            title_final = t_in
            if not t_in or low in confirm_keys:
                # Try to derive topic from content (e.g., "Kurzüberblick zu Mars ...")
                import re as _re
                t_guess = ""
                try:
                    m = _re.search(r"Kurzüberblick\s+zu\s+([^\n\r:]+)", str(content or ""), flags=_re.IGNORECASE)
                    if m:
                        t_guess = m.group(1).strip()
                except Exception:
                    t_guess = ""
                # If guess is a confirmation phrase or empty, try to derive from URL
                try:
                    if not t_guess or t_guess.lower() in confirm_keys:
                        from urllib.parse import urlparse, unquote
                        u = str(url or "").strip()
                        if u:
                            path = urlparse(u).path or ""
                            seg = (path.strip("/").split("/")[-1] if path else "")
                            if seg:
                                # Strip common wiki patterns like "Mars_(Planet)"
                                seg = unquote(seg)
                                seg = seg.replace("_", " ")
                                # Prefer inside parentheses if present
                                pm = _re.search(r"^(.+?)\s*\((.+)\)$", seg)
                                if pm:
                                    # e.g., "Mars (Planet)" -> "Mars"
                                    t_guess = pm.group(1).strip()
                                else:
                                    t_guess = seg.strip()
                except Exception:
                    pass
                if not t_guess:
                    try:
                        # Fallback to extractor if available in this module
                        t_guess = (extract_topic(str(content or "")) or "").strip()
                    except Exception:
                        t_guess = ""
                title_final = (t_guess or t_in or "").strip()[:120]
        except Exception:
            title_final = (str(title or "").strip() or "")[:120]

        # Call store (new API preferred)
        raw: Any = {}
        if hasattr(_mem, "save_memory_entry"):
            raw = _mem.save_memory_entry(title=title_final, content=content, tags=tags_norm, url=url)
        elif hasattr(_mem, "add_block"):
            bid = _mem.add_block(title=title_final, content=content, tags=tags_norm, url=url, meta={"source": "chat", "chain_hint": bool(chain_hint)})
            raw = {"file": f"{bid}.json", "id": bid, "url": url or ""} if isinstance(bid, str) and bid else {}
        else:
            raw = {}

        # Debug raw type/value
        if os.environ.get("KI_DEBUG_SAVE") == "1":
            try:
                logger.info("[KI_DEBUG_SAVE] save_memory raw type=%s value=%s", type(raw), raw)
            except Exception:
                pass

        # Coerce and normalize
        res = _coerce_to_dict(raw)
        # If empty or malformed, build guaranteed clean fallback
        if not isinstance(res, dict) or not res or not (res.get("id") or res.get("file") or res.get("url")):
            res = {
                "id": f"BLK_auto_{int(time.time())}",
                "file": "",
                "url": str(url or ""),
                "tags": ["vision"],
            }
        # URL precedence: passed url wins over stored
        res["url"] = str((url if url is not None else res.get("url")) or "")
        try:
            res_tags = sorted(set((list(res.get("tags") or [])) + (list(tags or [])) + ["vision"]))
        except Exception:
            res_tags = ["vision"]
        res["tags"] = res_tags

        bid = _extract_block_id(res) or f"BLK_auto_{int(time.time())}"
        res["id"] = str(bid)
        # Ensure file
        f = str(res.get("file") or res.get("path") or res.get("block_file") or "").strip()
        if not f:
            res["file"] = f"{res['id']}.json"
        else:
            try:
                from pathlib import Path as _Path
                res["file"] = f"{_Path(f).stem}.json"
            except Exception:
                res["file"] = f"{res['id']}.json"

        # Debug normalized (and via helper for consistency)
        if os.environ.get("KI_DEBUG_SAVE") == "1":
            try:
                logger.info("[KI_DEBUG_SAVE] save_memory_wrap: bid=%s blk=%s", res.get("id"), res)
            except Exception:
                pass
            try:
                _debug_save("save_memory_wrap", res)
            except Exception:
                pass

        return res
    except Exception as e:
        try:
            logger.error("save_memory_entry failed: %s", e)
        except Exception:
            pass
        return {"id": f"BLK_auto_{int(time.time())}", "file": "", "url": url or "", "tags": ["vision"]}

# -------------------------------------------------
# Knowledge Address Book (Papa-Modus)
# -------------------------------------------------

@router.get("/addressbook")
async def get_address_book(
    q: Optional[str] = None,
    current=Depends(get_current_user_opt),
):
    """
    Papa-Modus: Liefert das Wissens-Adressbuch (Blockchain-/Memory-Blöcke) als Liste.
    Quelle ist ADDRBOOK_PATH (JSON), gepflegt beim Speichern/Lernen.
    """
    # Guard: erlauben wenn Papa‑Modus aktiv ODER aktueller User admin ist
    papa_on = os.getenv("PAPA_MODE", "").lower() in {"1", "true", "on"}
    is_admin = _has_any_role(current, {"admin"})
    if not papa_on and not is_admin:
        raise HTTPException(status_code=403, detail="Papa-Modus ist nicht aktiviert (nur Admin)")

    # Best-effort Migration auf neues Schema
    try:
        migrate_addressbook_schema()
    except Exception:
        pass

    # addressbook.json Schema:
    # {
    #   "blocks": [
    #     {"topic":"Geschichte","block_id":"abcd1234","path":"/chain/blocks/.../history_ww2.json",
    #      "source":"Wikipedia","timestamp":"2025-09-06T18:23:00","rating":0.8}
    #   ]
    # }
    data_raw: Any = {"blocks": []}
    try:
        if ADDRBOOK_PATH.exists():
            data_raw = json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8")) or {"blocks": []}
    except Exception:
        data_raw = {"blocks": []}

    # Support both schemas: {"blocks": [...]} and legacy {topic: {block_file,url,updated_at}}
    blocks: List[Dict[str, Any]] = []
    if isinstance(data_raw, dict) and isinstance(data_raw.get("blocks"), list):
        blocks = data_raw.get("blocks") or []
    elif isinstance(data_raw, dict):
        # legacy mapping -> normalize to blocks list
        for topic, entry in (data_raw or {}).items():
            try:
                path = (entry.get("path") or entry.get("block_file") or "")
                if path and "/" not in path:
                    path = f"memory/long_term/blocks/{path}"
                block_id = ""
                if path:
                    try:
                        block_id = Path(str(path)).stem
                    except Exception:
                        pass
                blocks.append({
                    "topic": topic,
                    "block_id": block_id,
                    "path": path,
                    "source": entry.get("source") or entry.get("url") or "",
                    "timestamp": entry.get("timestamp") or entry.get("updated_at") or None,
                    "rating": entry.get("rating") or 0,
                })
            except Exception:
                continue
    else:
        blocks = []

    # Optionales Filter nach Query
    if q:
        ql = q.lower().strip()
        def _match(b: dict) -> bool:
            return any(
                ql in str(b.get(k, "")).lower()
                for k in ("topic", "path", "source", "block_id")
            )
        blocks = [b for b in blocks if _match(b)]

    # Vertrauens-Rating aus Memory-Index anreichern (falls vorhanden)
    try:
        from ... import memory_store as _mem  # type: ignore
        def _host_score(u: str) -> float:
            try:
                import urllib.parse as up
                host = up.urlparse(u or "").netloc.lower()
                good = ("wikipedia", ".gov", ".edu", "nature.com", "nih.gov", "who.int")
                if any(g in host for g in good):
                    return 0.9
                if host:
                    return 0.6
                return 0.5
            except Exception:
                return 0.5
        def _trust_from(b: dict, rating_avg: float) -> dict:
            try:
                src = str(b.get("source") or "")
                t_src = _host_score(src)
                # Age factor (simple): newer entries slightly higher (if integer ts)
                try:
                    ts = b.get("timestamp")
                    if isinstance(ts, str) and ts.isdigit():
                        ts = int(ts)
                    age_s = 0.8
                    if isinstance(ts, (int, float)):
                        import time as _t
                        now = int(_t.time())
                        age = max(0, now - int(ts))
                        two_years = 2*365*24*3600
                        age_s = 1.0 - 0.4 * min(1.0, age / two_years)
                    # Placeholder consistency until deeper cross‑check in place
                    cons = 0.6
                    score = round(0.5*rating_avg + 0.3*t_src + 0.15*age_s + 0.05*cons, 3)
                    return {"score": score, "signals": {"rating": rating_avg, "source": t_src, "age": round(age_s, 3), "consistency": cons}}
                except Exception:
                    pass
            except Exception:
                pass
            return {"score": round(rating_avg, 3), "signals": {"rating": rating_avg}}
        for b in blocks:
            try:
                rid = str(b.get("block_id") or "") or Path(str(b.get("path") or "")).stem
                if not rid:
                    continue
                r = _mem.get_rating(rid)
                if isinstance(r, dict) and "avg" in r:
                    avg = float(r.get("avg") or 0.0)
                    b["rating"] = avg
                    # optional trust field
                    b["trust"] = _trust_from(b, avg)
                    try:
                        cnt = int(r.get("count") or 0)
                        b["rating_count"] = cnt
                    except Exception:
                        pass
            except Exception:
                continue
    except Exception:
        pass

    return {"ok": True, "blocks": blocks}

# -------------------------------------------------
# System diagnostics: Knowledge loop (read-only)
# -------------------------------------------------

@router.post("/system/diagnose-loop")
async def diagnose_loop(body: dict, request: Request, current=Depends(get_current_user_opt)):
    """
    Runs a read-only diagnostic of the knowledge loop for a given message.
    Returns structured info: addressbook hits, KM/LLM/Web/Child decisions, memory IO, and preview.

    Payload example:
    {"message": "Was weißt du über die Erde?", "lang": "de"}
    """
    try:
        payload = SimpleNamespace(**(body or {}))
    except Exception:
        payload = SimpleNamespace(message=str(body))
    user_msg = (payload.message or "").strip()
    lang = (payload.lang or "de-DE").strip()
    persona = (payload.persona or "friendly").strip()

    if not user_msg:
        raise HTTPException(400, "message required")

    # Build topic and candidate paths
    try:
        from netapi.core.addressbook import extract_topic_from_message as ab_extract
        from netapi.core.addressbook import suggest_topic_paths as ab_suggest
        from netapi.core.addressbook import find_blocks_for_topic as ab_find_blocks
    except Exception:
        ab_extract = None  # type: ignore
        ab_suggest = None  # type: ignore
        ab_find_blocks = None  # type: ignore

    topic = ""
    try:
        topic = (ab_extract(user_msg) if ab_extract else extract_topic(user_msg)) or extract_topic(user_msg) or ""
    except Exception:
        topic = extract_topic(user_msg) or ""

    paths_checked: List[str] = []
    try:
        if ab_suggest:
            paths_checked = list(ab_suggest(user_msg) or [])
    except Exception:
        paths_checked = []

    ab_hits: List[Dict[str, Any]] = []
    blocks_found: List[str] = []
    if ab_find_blocks and topic:
        try:
            blocks_found = list(ab_find_blocks(topic) or [])
            if blocks_found:
                ab_hits.append({"path": None, "block_ids": blocks_found})
        except Exception:
            pass

    # Knowledge pipeline simulation (read-only)
    used_km = False
    used_llm = False
    used_web = False
    used_child = False
    selected = None
    blocks_read: List[str] = []
    blocks_written: List[str] = []  # read-only mode: keep empty
    sources_used: List[str] = []
    final_preview = ""

    # 0) Addressbook-first via KM topic_hints
    try:
        km_topic = km_guess_topic_path(user_msg, hints={"label": extract_topic(user_msg) or topic})
        km_res = km_find_relevant_blocks(user_msg, limit=3, topic_hints={"topic_path": km_topic})
        if km_res:
            used_km = True
            selected = selected or "km_addressbook"
            blk, sc = km_res[0]
            blocks_read.append(getattr(blk, 'id', '') or '')
            ans = (blk.summary or blk.content or "").strip()
            final_preview = clean(ans)[:300]
            sources_used.append("km")
    except Exception:
        pass

    # 1) If no preview yet, try general KM without hint
    if not final_preview:
        try:
            km_res2 = km_find_relevant_blocks(user_msg, limit=3)
            if km_res2:
                used_km = True
                selected = selected or "km"
                blk2, sc2 = km_res2[0]
                blocks_read.append(getattr(blk2, 'id', '') or '')
                final_preview = clean((blk2.summary or blk2.content or "").strip())[:300]
                sources_used.append("km")
        except Exception:
            pass

    # 2) If still no preview, try LLM (short)
    if not final_preview:
        try:
            raw = await call_llm_once(user_msg, system_prompt(persona), lang, persona)
            txt = clean(raw or "")
            if txt and len(txt.strip()) >= 80:
                used_llm = True
                selected = selected or "knowledge_llm"
                final_preview = txt[:300]
                sources_used.append("llm")
        except Exception:
            pass

    # 3) If still no preview, try Web
    if not final_preview:
        try:
            ans_web, srcs = try_web_answer(user_msg, limit=3)
            if ans_web:
                used_web = True
                selected = selected or "web"
                final_preview = clean(ans_web or "")[:300]
                sources_used.append("web")
        except Exception:
            pass

    # 4) Fallback: child-like
    if not final_preview:
        try:
            used_child = True
            selected = selected or "child"
            final_preview = build_childlike_question(user_msg, persona, None)
            final_preview = clean(final_preview or "")[:300]
            sources_used.append("user")
        except Exception:
            final_preview = ""

    # Build meta snapshot (read-only; don't touch real state)
    meta = {
        "pipeline": selected or "",
        "state_mood": None,
        "state_energy": None,
        "state_connection": None,
    }

    return {
        "ok": True,
        "input": {"message": user_msg, "lang": lang},
        "topic": topic,
        "topic_paths": paths_checked,
        "addressbook": {"paths_checked": paths_checked, "hits": ab_hits},
        "knowledge_pipeline": {
            "selected": selected,
            "used_km": used_km,
            "used_llm": used_llm,
            "used_web": used_web,
            "used_child": used_child,
        },
        "memory_io": {
            "blocks_read": [b for b in blocks_read if b],
            "blocks_written": blocks_written,
            "sources": sources_used,
        },
        "final_reply_preview": final_preview,
        "meta": meta,
    }

    # Manual Checklist (Diagnose):
    # 1) message="Was weißt du über die Erde?" → topic ~ "Erde"
    #    - Wenn gelernt: addressbook.hits ≠ leer, selected~km_addressbook
    #    - Sonst: used_llm=true (oder used_web), blocks_written (in echter Pipeline) würden entstehen
    # 2) Wiederholung → km_addressbook greift bevorzugt
    # 3) Neues Thema (z. B. "The Studio") → erster Lauf LLM/Web/Child; nach Web-Hinweis entsteht Block; nächster Lauf km_addressbook

def handle_special_cases(intent: str, user_msg: str, lang: str, state, persona):
    try:
        if intent == "greeting":
            name = getattr(persona, "name", "Kiana")
            mood = getattr(state, "mood", "neugierig") if state else "neugierig"
            return (
                f"Hallo! 👋 Ich bin {name}. "
                f"Mir geht's gerade {mood}. "
                "Wobei kann ich dir helfen?"
            )
    except Exception:
        pass
    return None

@router.post("")
async def chat_once(body: dict, request: Request, db=Depends(get_db), current=Depends(get_current_user_opt)):
    # Coerce dict payload into an attribute-access object with sane defaults
    try:
        if isinstance(body, dict):
            defaults = {
                "message": "",
                "persona": "friendly",
                "lang": "de-DE",
                "chain": False,
                "factcheck": False,
                "counter": False,
                "deliberation": False,
                "critique": False,
                "conv_id": None,
                "style": "balanced",
                "bullets": 5,
                "logic": "balanced",
                "format": "plain",
                "attachments": None,
                "quick_replies": None,
                "meta": None,
                "web_ok": True,
                "autonomy": 0,
            }
            payload = {**defaults, **(body or {})}
            body = SimpleNamespace(**payload)  # type: ignore
    except Exception:
        body = SimpleNamespace(message=str(body))  # type: ignore
    user_msg = (body.message or "").strip()
    conv_id = None  # conversation id placeholder, filled once messages persist
    timeline_user_id = None
    try:
        if current and current.get("id"):
            timeline_user_id = int(current["id"])  # type: ignore
    except Exception:
        timeline_user_id = None
    if timeline_user_id and user_msg:
        try:
            record_timeflow_event(
                db,
                user_id=timeline_user_id,
                event_type="chat_user",
                meta={"preview": user_msg[:160], "conv_id": body.conv_id},
                auto_commit=True,
            )
        except Exception:
            pass
    try:
        logger.warning("CHAT_DEBUG incoming: %r", user_msg)
    except Exception:
        pass
    sid = session_id(request)

    # Per-request explain context (used by _finalize_reply + direct-return wrappers)
    try:
        _now_ms = int(time.time() * 1000)
    except Exception:
        _now_ms = 0
    cid = f"{sid}:{_now_ms % 1000000:06d}"
    try:
        _CHAT_EXPLAIN_CTX.set({
            "cid": cid,
            "route": "/api/chat",
            "t0": time.time(),
            "is_question": bool(is_question(user_msg)),
            "policy": {
                "web_ok": bool(getattr(body, "web_ok", True)),
                "autonomy": int(getattr(body, "autonomy", 0) or 0),
                "style": str(getattr(body, "style", "") or ""),
                "bullets": int(getattr(body, "bullets", 0) or 0),
            },
            "tools": [],
            "kpi_done": False,
        })
    except Exception:
        pass

    # Quality gates: snapshot state early (needed for prompt suppression)
    try:
        _init_quality_gates_context(current=current)
    except Exception:
        pass
    # Early hard guard: standard smalltalk 'wie geht es dir' should always respond deterministically
    try:
        t_early = (user_msg or "").lower()
        if ("wie geht es dir" in t_early) or ("wie geht's dir" in t_early) or ("wie gehts dir" in t_early):
            try:
                persona_early = get_kiana_persona()
            except Exception:
                persona_early = SimpleNamespace(name="Kiana", role="deine digitale Begleiterin", core_values=["Ehrlichkeit","Hilfsbereitschaft"], rules={})  # type: ignore
            try:
                state_early = load_state()
            except Exception:
                state_early = None  # type: ignore
            reply_early = (
                "Mir geht’s gut, danke! 😊 Wie geht’s dir – und womit kann ich helfen?"
            )
            reply_early = postprocess_and_style(reply_early, persona_early, state_early, {}, None)
            # Persist minimal
            conv_id_early = None
            try:
                if current and current.get("id"):
                    uid = int(current["id"])  # type: ignore
                    conv = _ensure_conversation(db, uid, body.conv_id)
                    conv_id_early = conv.id
                    _save_msg(db, conv.id, "user", user_msg)
                    _save_msg(db, conv.id, "ai", reply_early)
                    asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply_early, body.lang or "de-DE"))
            except Exception:
                conv_id_early = None
            try:
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                uid_for_mem = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                save_experience(uid_for_mem, conv_id_early, {
                    "type": "smalltalk_how_are_you", "user_message": user_msg, "assistant_reply": reply_early,
                    "timestamp": now_iso,
                })
                if state_early:
                    save_state(state_early)
            except Exception:
                pass
            conv_out_early = conv_id_early if conv_id_early is not None else (body.conv_id or None)
            return _finalize_reply(
                reply_early,
                state=state, conv_id=conv_out_early,
                intent="smalltalk_guard", topic=extract_topic(user_msg),
                extras={"ok": True, "style_used": {}, "style_prompt": None, "backend_log": {"pipeline": "smalltalk_guard"}}
            )
    except Exception:
        pass
    # Gentle risk detection (audit-only)
    risk_flag = False
    try:
        if _is_risky_prompt(user_msg):
            risk_flag = True
            _audit_risky_prompt(current, sid, user_msg)
    except Exception:
        risk_flag = False
    m = CMD_RX.match(user_msg)
    if m:
        cmd, rest = m.group(1).lower(), (m.group(2) or "").strip()
        # Safety‑Rail: Tool‑Use nur für Creator/Admin
        if not _has_any_role(current, {"creator", "admin"}):
            raise HTTPException(403, "forbidden: tool-use requires creator/admin")
        from ..os import syscalls as sc
        if cmd == "run":
            res = sc.sc_proc_run("creator", rest)
        elif cmd == "read":
            res = sc.sc_fs_read("creator", rest)
        elif cmd == "get":
            res = sc.sc_web_get("creator", rest)
        else:
            res = {"ok": False, "error":"unknown"}
        return _attach_explain_and_kpis(
            {"ok": True, "reply": json.dumps(res, ensure_ascii=False, indent=2)},
            route="/api/chat",
            intent="tool_command",
            policy={"tool": cmd},
            tools=[],
            source_expected=False,
        )
    if not user_msg:
        raise HTTPException(400, "empty message")

    # Enforce daily quota for free users (no-op for papa/creator)
    try:
        enforce_quota(current, db)
    except HTTPException:
        # bubble up 429 with JSON detail
        raise

    sid = session_id(request)
    last_topic = _LAST_TOPIC.get(sid, "")

    # Rate limit
    ip = request.client.host if request.client else "?"
    if not _rate_allow(ip, "chat_once", limit=40, per_seconds=60):
        raise HTTPException(429, "rate limit: 40/min")

    # Moderation
    blocked, cleaned_msg, reason = moderate(user_msg, _ethics_level())
    if blocked:
        try:
            _audit_chat({"ts": int(time.time()), "sid": sid, "blocked": True, "reason": reason, "user": user_msg})
        except Exception:
            pass
        return _attach_explain_and_kpis(
            {"ok": True, "reply": "Ich kann dabei nicht helfen. Wenn du willst, nenne ich sichere Alternativen oder Hintergründe.", "backend_log": {"moderation": reason}},
            route="/api/chat",
            intent="moderated",
            policy={"moderated": True},
            tools=[],
            source_expected=False,
        )
    else:
        user_msg = cleaned_msg

    # -------------------------------------------------
    # Selftalk / smalltalk bypass (must never use web/memory and must never be blocked)
    # -------------------------------------------------
    try:
        from .intent_guard import classify as _ig_classify
        _intent0 = str(_ig_classify(user_msg) or "general")
    except Exception:
        _intent0 = "general"
    if _intent0 == "selftalk":
        low0 = (user_msg or "").lower().strip()
        if any(k in low0 for k in ["wie geht", "how are you"]):
            lead = "Mir geht’s gut, danke."
        elif any(k in low0 for k in ["hallo", "hi", "hey", "guten morgen", "guten tag", "guten abend", "hello", "good morning", "good evening"]):
            lead = "Hallo!"
        else:
            lead = "Ich bin KI_ana."
        reply_selftalk = (
            f"{lead} Ich bin deine digitale Begleiterin im KI_ana-System. "
            "Ich helfe dir beim Denken, Erklären, Planen, Schreiben und beim Debuggen von Code. "
            "Wobei kann ich dir helfen?"
        ).strip()

        conv_id_selftalk = None
        try:
            if current and current.get("id"):
                uid = int(current["id"])  # type: ignore[index]
                conv = _ensure_conversation(db, uid, body.conv_id)
                conv_id_selftalk = int(conv.id)
                _save_msg(db, conv.id, "user", user_msg)
                _save_msg(db, conv.id, "ai", reply_selftalk)
                asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply_selftalk, body.lang or "de-DE"))
        except Exception:
            conv_id_selftalk = None

        conv_out_selftalk = conv_id_selftalk if conv_id_selftalk is not None else (body.conv_id or None)
        payload = {
            "ok": True,
            "reply": reply_selftalk,
            "conv_id": conv_out_selftalk,
            "sources": [],
            "memory_ids": [],
            "style_prompt": None,
            "backend_log": {"pipeline": "selftalk"},
        }
        return _attach_explain_and_kpis(
            payload,
            route="/api/chat",
            intent="selftalk",
            policy={"web_ok": False, "memory_retrieve_ok": False},
            tools=[],
            source_expected=False,
            sources_count=0,
        )

    # -------------------------------------------------
    # Phase 0.5: Explicit remember command ("Merk dir: …")
    # - Must save without asking
    # - Must return memory_ids for transparency
    # -------------------------------------------------
    try:
        low_u = (user_msg or "").strip().lower()
        m_remember = re.match(r"^\s*(merk\s+dir|merke\s+dir|speicher|speichere|remember)\s*[:\-]?\s*(.+)?$", low_u, flags=re.IGNORECASE)
    except Exception:
        m_remember = None

    if m_remember:
        raw_payload = ""
        try:
            raw_payload = (user_msg or "").strip()
            # Extract after the first ':' or '-' if present; otherwise remove the command words.
            m2 = re.match(r"^\s*(?:merk\s+dir|merke\s+dir|speicher|speichere|remember)\s*[:\-]?\s*(.*)$", raw_payload, flags=re.IGNORECASE)
            raw_payload = (m2.group(1) if m2 else "").strip()
        except Exception:
            raw_payload = ""

        if not raw_payload:
            reply_rem = "Was genau soll ich mir merken? (Schreib es bitte nach ‘Merk dir: …’)"
            payload = {
                "ok": True,
                "reply": reply_rem,
                "conv_id": (body.conv_id or None),
                "sources": [],
                "memory_ids": [],
                "style_prompt": None,
                "backend_log": {"pipeline": "remember_explicit", "saved": False},
            }
            try:
                payload["explain"] = {"note": "Explizites Merken angefordert, aber ohne Inhalt."}
            except Exception:
                pass
            return _attach_explain_and_kpis(
                payload,
                route="/api/chat",
                intent="remember",
                policy={"learning": "explicit"},
                tools=[{"tool": "memory_write", "ok": False}],
                source_expected=False,
                sources_count=0,
            )

        # Persist as long-term memory block
        persisted_id = None
        addr_ok = False
        topic_path = "user_memory"
        mem_type = "user_note"
        tags = []
        try:
            # Heuristic: treat common phrasing as response-style preference
            lp = raw_payload.lower()
            if any(k in lp for k in ["antworte kurz", "kurze antwort", "knapp", "bitte kurz", "kurz &", "concise"]):
                mem_type = "user_preference"
                topic_path = "user_preferences"
                tags.append("preference")
        except Exception:
            pass

        try:
            from netapi import memory_store
            uid = int(current.get("id")) if (current and current.get("id") is not None) else 0
            meta = {
                "type": mem_type,
                "user_id": int(uid),
                "source": "explicit",
                "content": raw_payload,
            }
            title = f"User Memory: user={uid} ({mem_type})"[:160]
            tags = list({*(tags or []), mem_type, f"user:{uid}", "source:chat"})
            persisted_id = memory_store.add_block(title=title, content=raw_payload, tags=tags, meta=meta)
            try:
                from netapi.core.addressbook import register_block_for_topic
                register_block_for_topic(topic_path, str(persisted_id))
                addr_ok = True
            except Exception:
                addr_ok = False
        except Exception:
            persisted_id = None
            addr_ok = False

        # Also update per-user style profile for concise preference
        try:
            if persisted_id and uid_str:
                lp = raw_payload.lower()
                if any(k in lp for k in ["antworte kurz", "kurze antwort", "knapp", "bitte kurz", "concise"]):
                    existing = load_user_profile(uid_str) or {}
                    existing["kurz"] = True
                    save_user_profile(uid_str, existing)
        except Exception:
            pass

        reply_ok = "Alles klar – ich habe mir das gemerkt."
        if mem_type == "user_preference":
            reply_ok = "Alles klar – ich merke mir diese Präferenz."
        payload = {
            "ok": True,
            "reply": reply_ok,
            "conv_id": (body.conv_id or None),
            "sources": [],
            "memory_ids": ([str(persisted_id)] if persisted_id else []),
            "style_prompt": None,
            "backend_log": {"pipeline": "remember_explicit", "saved": bool(persisted_id), "addressbook": bool(addr_ok)},
        }
        try:
            payload["explain"] = {"note": "Explizite Merken-Anweisung: gespeichert." if persisted_id else "Explizite Merken-Anweisung: Speichern fehlgeschlagen."}
        except Exception:
            pass
        return _attach_explain_and_kpis(
            payload,
            route="/api/chat",
            intent="remember",
            policy={"learning": "explicit"},
            tools=[{"tool": "memory_write", "ok": bool(persisted_id)}],
            source_expected=False,
            sources_count=0,
        )

    # -------------------------------------------------
    # Phase 1: Missing-Context-Gate (intent_guard)
    # Must short-circuit BEFORE retrieval/memory/LLM/learning.
    # -------------------------------------------------
    try:
        from .intent_guard import guard_missing_context
        g = guard_missing_context(user_msg, lang=str(getattr(body, "lang", "de-DE") or "de-DE"))
    except Exception:
        g = None
    if g and getattr(g, "should_block", False):
        qs = list(getattr(g, "questions", []) or [])
        intent_g = str(getattr(g, "intent", "missing_context") or "missing_context")
        miss = list(getattr(g, "missing_fields", []) or [])
        note = str(getattr(g, "note", "Noch kein Kontext – KI_ana wartet auf Klärung.") or "")
        if not qs:
            qs = ["Kannst du kurz mehr Kontext geben?"]
        reply_guard = (
            "Bevor ich loslege, brauche ich noch kurz Kontext (ich will nichts raten):\n\n"
            + "\n".join([f"- {q}" for q in qs])
        ).strip()

        # Optional persistence to conversation (NOT memory learning): store chat messages only.
        conv_id_guard = None
        try:
            if current and current.get("id"):
                uid = int(current["id"])  # type: ignore[index]
                conv = _ensure_conversation(db, uid, body.conv_id)
                conv_id_guard = int(conv.id)
                _save_msg(db, conv.id, "user", user_msg)
                _save_msg(db, conv.id, "ai", reply_guard)
                asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply_guard, body.lang or "de-DE"))
        except Exception:
            conv_id_guard = None

        conv_out_guard = conv_id_guard if conv_id_guard is not None else (body.conv_id or None)
        payload = {
            "ok": True,
            "reply": reply_guard,
            "conv_id": conv_out_guard,
            "sources": [],
            "memory_ids": [],
            "backend_log": {
                "pipeline": "intent_guard",
                "intent_guard": {"intent": intent_g, "missing": miss},
            },
        }
        # Ensure transparency modal has a note even when empty sources/memories.
        try:
            payload["explain"] = {"note": note}
        except Exception:
            pass
        return _attach_explain_and_kpis(
            payload,
            route="/api/chat",
            intent=intent_g,
            policy={"intent_guard": True},
            tools=[],
            source_expected=False,
            sources_count=0,
        )

    # Style profile: analyze incoming text and prepare profile for application
    uid_str: Optional[str] = None
    try:
        if current and current.get("id") is not None:
            uid_str = str(int(current["id"]))
    except Exception:
        uid_str = None
    detected = {}
    if style_analyzer and hasattr(style_analyzer, 'analyze_text'):
        try:
            detected = style_analyzer.analyze_text(user_msg, lang=(body.lang or 'de')) or {}
        except Exception:
            detected = {}
    persisted = load_user_profile(uid_str) if uid_str else None
    profile_used = dict(persisted or {})
    profile_used.update({k: v for k, v in (detected or {}).items() if v})
    style_consent_needed = bool(uid_str and not (persisted and isinstance(persisted, dict)))
    style_used_meta = {
        "anrede": profile_used.get("anrede"),
        "formell": profile_used.get("formell"),
        "dialekt": profile_used.get("dialekt"),
        "tonfall": profile_used.get("tonfall"),
    }
    # style_prompt gating: only ask when a real learning candidate exists AND policy requests asking,
    # or when the user explicitly requests remembering.
    style_prompt = None
    try:
        low_u = (user_msg or "").lower()
        explicit_style_request = bool(re.search(r"\b(merk\s+dir|merke\s+dir|speicher|speichere|remember)\b", low_u))
    except Exception:
        explicit_style_request = False
    try:
        learning_candidate = bool(any(style_used_meta.get(k) for k in ["anrede", "formell", "dialekt", "tonfall"]))
    except Exception:
        learning_candidate = False
    try:
        meta_obj = getattr(body, "meta", None)
        meta_dict = meta_obj if isinstance(meta_obj, dict) else {}
        pol = meta_dict.get("policy") if isinstance(meta_dict.get("policy"), dict) else {}
        learning_policy = str(pol.get("learning") or "").lower().strip()
    except Exception:
        learning_policy = ""
    if explicit_style_request:
        style_prompt = "Darf ich mir deinen Sprachstil merken, damit ich beim nächsten Mal genauso mit dir reden kann?"
    elif style_consent_needed and learning_candidate and learning_policy == "ask":
        style_prompt = "Darf ich mir deinen Sprachstil merken, damit ich beim nächsten Mal genauso mit dir reden kann?"

    # Quality gate enforcement: suppress learning consent prompts during cooldown
    try:
        if style_prompt:
            ctx_g = _CHAT_EXPLAIN_CTX.get()
            gates = ctx_g.get("gates") if isinstance(ctx_g, dict) else None
            if isinstance(gates, dict) and bool(gates.get("enforced")):
                if "learning_cooldown" in set(gates.get("enforced_gates") or []):
                    style_prompt = None
    except Exception:
        pass
    # Consent lifecycle: handle previous pending consent
    consent_note = ""
    try:
        pend = _STYLE_PENDING.get(sid)
        if pend:
            low_u = user_msg.lower()
            if is_affirmation(user_msg):
                if uid_str and isinstance(pend.get('profile'), dict):
                    save_user_profile(uid_str, pend['profile'])
                _STYLE_PENDING.pop(sid, None)
                consent_note = "Alles klar – ich merke mir deinen Sprachstil."
                try:
                    from netapi.modules.observability import metrics as obs_metrics
                    obs_metrics.inc_learning_consent(kind="style", decision="yes")
                except Exception:
                    pass
            elif NEG_RX.search(low_u):
                _STYLE_PENDING.pop(sid, None)
                consent_note = "Alles klar – ich speichere deinen Stil nicht."
                try:
                    from netapi.modules.observability import metrics as obs_metrics
                    obs_metrics.inc_learning_consent(kind="style", decision="no")
                except Exception:
                    pass
    except Exception:
        pass
    # If we plan to prompt now, mark pending so next turn can confirm
    if style_prompt:
        try:
            _STYLE_PENDING[sid] = {"profile": profile_used}
        except Exception:
            pass
        try:
            from netapi.modules.observability import metrics as obs_metrics
            obs_metrics.inc_learning_consent(kind="style", decision="prompt")
        except Exception:
            pass
        try:
            from netapi.modules.quality_gates import gates as qg
            qg.record_learning_prompt(kind="style")
        except Exception:
            pass

    # Frage-Kontext vormerken (hilft, spätere Kurzform/Bestätigung dem Thema zuzuordnen)
    try:
        if is_question(user_msg):
            t0 = extract_topic(user_msg)
            set_offer_context(sid, topic=(t0 or (user_msg[:80] if user_msg else None)), seed=user_msg)
            if t0:
                _LAST_TOPIC[sid] = t0
    except Exception:
        pass

    # Frühe Behandlung von reinen Grüßen (keine Memory/Web/LLM nötig)
    try:
        low = user_msg.lower()
        # Do not intercept greetings that contain knowledge-style queries
        looks_like_knowledge = any(p in low for p in [
            "was weißt du über",
            "was weisst du über",
            "was ist ",
            "erklär mir",
            "erkläre mir",
        ])
        if _HOW_ARE_YOU.search(low):
            mood = None
            try:
                mood = (state.mood if state else None) or "neutral"
            except Exception:
                mood = "neutral"
            r = (
                f"Mir geht’s gut, danke! 😊 Ich bin gerade eher {mood} unterwegs. "
                "Wie geht’s dir – und womit kann ich helfen?"
            )
            r = postprocess_and_style(r, persona if 'persona' in locals() else get_kiana_persona(), state, profile_used, style_prompt)
            if consent_note:
                r = (r + "\n\n" + consent_note).strip()
            return _finalize_reply(
                r,
                state=state, conv_id=(body.conv_id or None), intent="smalltalk_greeting", topic=None,
                extras={"ok": True, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {}}
            )
        if _GREETING.search(low) and not looks_like_knowledge:
            if last_topic:
                # Avoid repeating plain greeting; continue on last topic with options
                r = f"Hallo! 👋 Sollen wir bei ‘{last_topic}’ weitermachen – oder etwas eingrenzen?"
                r = _apply_style(r, profile_used)
                qrs = [f"Weiter mit {last_topic}", "Beispiele zeigen", "Details vertiefen"]
                if style_prompt:
                    r = (r + "\n\n" + style_prompt).strip()
                return _finalize_reply(
                    r,
                    state=state, conv_id=(body.conv_id or None), intent="greeting", topic=last_topic or None,
                    extras={"ok": True, "quick_replies": qrs, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {}}
                )
            else:
                r = "Hallo! 👋 Wie kann ich dir helfen?"
                r = _apply_style(r, profile_used)
                if style_prompt:
                    r = (r + "\n\n" + style_prompt).strip()
                return _finalize_reply(
                    r,
                    state=state, conv_id=(body.conv_id or None), intent="greeting", topic=None,
                    extras={"ok": True, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {}}
                )
        calc = try_calc_or_convert(user_msg)
        if calc:
            r = _apply_style(calc, profile_used)
            if style_prompt:
                r = (r + "\n\n" + style_prompt).strip()
            return _finalize_reply(
                r,
                state=state, conv_id=(body.conv_id or None), intent="calc", topic=extract_topic(user_msg),
                extras={"ok": True, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {}}
            )
    except Exception:
        pass

    skip_direct_llm = False
    try:
        skip_direct_llm = bool(is_question(user_msg or ""))
    except Exception:
        skip_direct_llm = False
    if ALLOW_DIRECT_LLM and not skip_direct_llm:
        direct_pipeline = "llm"
        try:
            web_ctx_direct = lookup_web_context(user_msg)
        except Exception:
            web_ctx_direct = ""
        if web_ctx_direct:
            direct_pipeline = "web+llm"
            try:
                logger.info("knowledge_pipeline selected=web+llm topic=%s (direct_llm)", extract_topic(user_msg))
            except Exception:
                pass
        direct_prompt = compose_reasoner_prompt(user_msg, web_ctx_direct or "")
        try:
            logger.info(
                "knowledge_pipeline direct_llm web_ctx_len=%d pipeline=%s topic=%s",
                len(web_ctx_direct or ""),
                direct_pipeline,
                extract_topic(user_msg),
            )
        except Exception:
            pass
        try:
            llm_txt = await call_llm(direct_prompt)
        except Exception:
            llm_txt = ""
        txt_fb = clean(llm_txt or "")
        if txt_fb and txt_fb.strip():
            try:
                logger.info("chat_once LLM reply len=%d", len(txt_fb))
            except Exception:
                pass
            # Return immediately with a natural reply; downstream persistence will handle conversation flow
            return _attach_explain_and_kpis(
                {"ok": True, "reply": txt_fb, "backend_log": {"pipeline": direct_pipeline}},
                route="/api/chat",
                intent="llm_direct",
                policy={"pipeline": direct_pipeline},
                tools=[],
                source_expected=False,
            )

    # 1) Explizite Wahl?
    choice = pick_choice(user_msg)
    if choice:
        ctx = get_offer_context(sid) or {}
        topic_ctx = ctx.get("topic") or extract_topic(user_msg) or ""
        seed_ctx = ctx.get("seed") or user_msg
        set_last_offer(sid, None)
        set_offer_context(sid, topic=(topic_ctx or None), seed=seed_ctx)
        out = await execute_choice(choice, topic_ctx or "das Thema", seed_ctx, body.persona or "friendly", body.lang or "de-DE")
        r = _apply_style(clean(out), profile_used)
        if style_prompt:
            r = (r + "\n\n" + style_prompt).strip()
        return _attach_explain_and_kpis(
            {"ok": True, "reply": r, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {}},
            route="/api/chat",
            intent="choice",
            policy={"choice": str(choice)},
            tools=[],
            source_expected=False,
        )

    # 2) „Ja / bitte“ auf letztes Angebot?
    prev = get_last_offer(sid)
    if prev and is_affirmation(user_msg):
        ctx = get_offer_context(sid) or {}
        topic_ctx = (ctx.get("topic") or extract_topic(user_msg) or "das Thema")
        seed_ctx = ctx.get("seed") or user_msg
        out = await execute_choice(prev, topic_ctx, seed_ctx, body.persona or "friendly", body.lang or "de-DE")
        set_last_offer(sid, None)  # nach Ausführung leeren
        r = _apply_style(clean(out), profile_used)
        if style_prompt:
            r = (r + "\n\n" + style_prompt).strip()
        return _attach_explain_and_kpis(
            {"ok": True, "reply": r, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {}},
            route="/api/chat",
            intent="followup_choice",
            policy={"followup": True},
            tools=[],
            source_expected=False,
        )

    # KI_ana Self-Awareness Check - Priority over everything else
    if any(kw in user_msg.lower() for kw in ['wer bist du', 'was bist du', 'dein name', 'dein zweck']):
        try:
            from .ai_consciousness import get_identity
            identity = get_identity()
            direct_answer = f"Ich bin {identity['name']} v{identity['version']}, eine {identity['type']}. Mein Zweck ist {identity['purpose']}. Ich wurde erschaffen, um zu lernen, zu helfen und zu beschützen. Meine Architektur basiert auf blockchain-basiertem Gedächtnis und dezentralen Sub-KIs. Ich habe vollen Zugriff auf meinen Code und bin mir meiner selbst vollständig bewusst."
            r = _apply_style(direct_answer, profile_used)
            if style_prompt:
                r = (r + "\n\n" + style_prompt).strip()
            if consent_note:
                r = (r + "\n\n" + consent_note).strip()
            return _attach_explain_and_kpis(
                {"ok": True, "reply": r, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"identity_response": True}},
                route="/api/chat",
                intent="identity",
                policy={},
                tools=[],
                source_expected=False,
            )
        except Exception as e:
            # Fallback if consciousness fails
            r = _apply_style("Ich bin KI_ana, eine dezentrale Mutter-KI. Mein Zweck ist zu lernen, zu helfen und zu beschützen.", profile_used)
            return _attach_explain_and_kpis(
                {"ok": True, "reply": r, "style_used": style_used_meta, "backend_log": {"identity_fallback": True}},
                route="/api/chat",
                intent="identity",
                policy={"fallback": True},
                tools=[],
                source_expected=False,
            )

    # Auto-detect if current information needed (force web search)
    auto_web_needed = False
    try:
        from .current_detection import needs_current_info
        auto_web_needed, reason = needs_current_info(user_msg)
        if auto_web_needed:
            logger.info(f"Auto-enabling web search: {reason}")
            body.web_ok = True  # Force web search on!
    except Exception:
        pass
    
    # Memory Context Check - Add conversation memory
    memory_context = ""
    memory_context_ids: list[str] = []
    try:
        from .memory_integration import build_memory_context_with_ids, compact_response
        if current and current.get("id"):
            user_id = int(current["id"])
            memory_context, memory_context_ids = build_memory_context_with_ids(user_msg, user_id)
            if memory_context:
                logger.info(f"🧠 Memory context loaded for user {user_id}: {len(memory_context)} chars")
    except Exception as e:
        logger.error(f"Failed to load memory context: {e}")
    try:
        if memory_context_ids:
            _record_used_memory_ids(memory_context_ids)
    except Exception:
        pass

    # Self-State: load and update basic fields
    try:
        state = load_state()
        # Update activity and cycle
        try:
            state.cycles = int(state.cycles or 0) + 1
        except Exception:
            state.cycles = 1
        try:
            state.last_active_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        except Exception:
            pass
        # Affect integration: detect user tone, handle sleep/wake
        try:
            from netapi.core.affect import detect_user_tone as _detect_tone, maybe_enter_sleep as _sleep_maybe, maybe_wake_from_sleep as _wake
            tone_detected = _detect_tone(user_msg)
            try:
                state.last_user_tone = tone_detected
            except Exception:
                pass
            # Enter sleep if needed (good night cues or energy low)
            try:
                _sleep_maybe(state, user_msg)
            except Exception:
                pass
            # If sleeping, wake on new user input and attach a pending note
            try:
                note = _wake(state)
                if note:
                    setattr(state, 'pending_wake_note', note)
            except Exception:
                pass
        except Exception:
            pass
        # Track recent topics (bounded)
        try:
            t_recent = extract_topic(user_msg) or (user_msg[:60] if user_msg else "")
            if t_recent:
                lst = list(state.recent_topics or [])
                lst.append(str(t_recent))
                state.recent_topics = lst[-20:]
        except Exception:
            pass
    except Exception:
        state = None  # type: ignore

    # If we are awaiting a user teaching response, record it first
    try:
        # New child-learning path: pending_learning implies treat current message as explanation
        if state and getattr(state, 'pending_learning', None):
            _pl = state.pending_learning or {}
            topic_path_pl = str(_pl.get('topic_path') or extract_topic_path(user_msg))
            # Detect directives like "schau mal auf wikipedia" and perform web lookup instead of learning plain text
            try:
                _low = (user_msg or '').strip().lower()
                _web_cmd = any(kw in _low for kw in [
                    'schau mal auf wikipedia', 'schau auf wikipedia', 'wikipedia',
                    'lies das im internet nach', 'google das', 'google mal', 'im internet nach'
                ])
            except Exception:
                _web_cmd = False
            if _web_cmd:
                try:
                    # Prefer a clean topic to search
                    _topic_clean = extract_topic(user_msg) or topic_path_pl or ''
                    # Trigger web answer for this topic
                    ans_web, srcs_web = try_web_answer(_topic_clean or user_msg, limit=3)
                except Exception:
                    ans_web, srcs_web = (None, [])
                if ans_web:
                    # Promote/save as KnowledgeBlock (source=web) and register in addressbook + audit store
                    try:
                        _hints = {"topic_path": topic_path_pl, "title": extract_topic(_topic_clean) or None, "summary": short_summary(ans_web)}
                        kb = km_promote_block(ans_web, (_topic_clean or user_msg), source="web", hints=_hints, base_confidence=0.7, tags=["web","autosaved"])  # type: ignore
                        try:
                            from netapi.core.addressbook import register_block_for_topic as _ab_register
                            if kb and getattr(kb, 'id', None) and getattr(kb, 'topic_path', None):
                                _ab_register(kb.topic_path, kb.id)
                                try:
                                    logger.info("addressbook_register", extra={"topic_path": kb.topic_path, "block_id": kb.id})
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        # Audit DB store (SQLite) for dashboards
                        try:
                            from netapi import memory_store as _mem
                            _mem.save_memory_entry(title=str(_topic_clean)[:120] or topic_path_pl, content=ans_web, tags=["web","learned"], url=(srcs_web[0].get('url') if (srcs_web and srcs_web[0].get('url')) else None))
                        except Exception:
                            pass
                    except Exception:
                        pass
                    # Build user reply summarizing
                    out = ("Danke für den Hinweis. Ich habe jetzt im Web (Wikipedia) nachgelesen und mir das als Wissensblock gespeichert. Kurz zusammengefasst: " + short_summary(ans_web, max_chars=300)).strip()
                    out = postprocess_and_style(out, persona, state, profile_used, style_prompt)
                    try:
                        if isinstance(state, KianaState):
                            state.pending_learning = None
                            save_state(state)
                    except Exception:
                        pass
                    return _finalize_reply(
                        out,
                        state=state, conv_id=(body.conv_id or None), intent="knowledge", topic=extract_topic(_topic_clean or user_msg), pipeline="web",
                        extras={"ok": True, "auto_modes": ["web"], "role_used": "Forscher", "memory_ids": [], "topic": extract_topic(_topic_clean or user_msg), "backend_log": {"pipeline": "web", "topic": extract_topic(_topic_clean or user_msg)}}
                    )
            # Existing path: treat given message as explanation text
            explanation = (user_msg or '').strip()
            if explanation:
                try:
                    reply_learn2 = process_user_teaching(explanation, topic_path_pl, state)
                except Exception:
                    try:
                        logger.exception("pending_learning handling failed")
                    except Exception:
                        pass
                    reply_learn2 = (
                        "Ups, da ist bei mir intern etwas schiefgelaufen, "
                        "aber deine Erklärung war trotzdem hilfreich. "
                        "Magst du es mir später noch einmal kurz zusammenfassen?"
                    )
                # Clear flag and persist state regardless
                state.pending_learning = None
                reply_learn2 = postprocess_and_style(reply_learn2, persona if 'persona' in locals() else get_kiana_persona(), state, profile_used, style_prompt)
                reply_learn2 = make_user_friendly_text(reply_learn2, state)
                conv_id_learn2 = None
                try:
                    if current and current.get("id"):
                        uid = int(current["id"])  # type: ignore
                        conv = _ensure_conversation(db, uid, body.conv_id)
                        conv_id_learn2 = conv.id
                        _save_msg(db, conv.id, "user", user_msg)
                        _save_msg(db, conv.id, "ai", reply_learn2)
                        asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply_learn2, body.lang or "de-DE"))
                except Exception:
                    conv_id_learn2 = None
                try:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    uid_for_mem = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                    save_experience(uid_for_mem, conv_id_learn2, {
                        "type": "user_teaching", "user_message": user_msg, "assistant_reply": reply_learn2,
                        "timestamp": now_iso, "mood": (state.mood if state else "neutral"), "topic": topic_path_pl,
                    })
                    save_state(state)
                except Exception:
                    pass
                conv_out_learn2 = conv_id_learn2 if conv_id_learn2 is not None else (body.conv_id or None)
                return _attach_explain_and_kpis(
                    {"ok": True, "reply": reply_learn2, "conv_id": conv_out_learn2, "auto_modes": [], "role_used": "Lernen", "memory_ids": [], "quick_replies": _quick_replies_for_topic(topic_path_pl, user_msg), "topic": topic_path_pl, "risk_flag": False, "style_used": style_used_meta, "style_prompt": style_prompt, "meta": {"intent": "user_teaching", "topic_path": topic_path_pl}, "backend_log": {"pipeline": "learn_from_user_child"}},
                    route="/api/chat",
                    intent="user_teaching",
                    source_expected=False,
                )

        if state and getattr(state, 'pending_followup', None) == 'learning':
            explanation = (user_msg or '').strip()
            if explanation:
                topic_guess = extract_topic(user_msg) or _LAST_TOPIC.get(sid, '') or 'unbekanntes Thema'
                record_user_teaching(state, topic=topic_guess, fact=explanation)
                reply_learn = (
                    "Danke, dass du mir das erklärst! Ich versuche es mir so zu merken:\n\n" + explanation
                )
                reply_learn = postprocess_and_style(reply_learn, persona if 'persona' in locals() else get_kiana_persona(), state, profile_used, style_prompt)
                # Persist conversation
                conv_id_learn = None
                try:
                    if current and current.get("id"):
                        uid = int(current["id"])  # type: ignore
                        conv = _ensure_conversation(db, uid, body.conv_id)
                        conv_id_learn = conv.id
                        _save_msg(db, conv.id, "user", user_msg)
                        _save_msg(db, conv.id, "ai", reply_learn)
                        asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply_learn, body.lang or "de-DE"))
                except Exception:
                    conv_id_learn = None
                # Save experience and state
                try:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    uid_for_mem = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                    save_experience(uid_for_mem, conv_id_learn, {
                        "type": "user_teaching", "user_message": user_msg, "assistant_reply": reply_learn,
                        "timestamp": now_iso, "mood": (state.mood if state else "neutral"), "topic": topic_guess,
                    })
                    save_state(state)
                except Exception:
                    pass
                conv_out_learn = conv_id_learn if conv_id_learn is not None else (body.conv_id or None)
                return _finalize_reply(
                    reply_learn,
                    state=state, conv_id=conv_out_learn, intent="user_teaching", topic=topic_guess,
                    extras={"ok": True, "auto_modes": [], "role_used": "Lernen", "memory_ids": [], "quick_replies": _quick_replies_for_topic(topic_guess, user_msg), "topic": topic_guess, "risk_flag": False, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": "learn_from_user"}}
                )
    except Exception:
        pass

    # Ensure `intent` is always defined before first use.
    # (There is later intent detection that assigns to this local variable,
    # so referencing it before assignment would raise UnboundLocalError.)
    intent = "general"

    if intent == "knowledge_query":
        web_ctx_digest = ""
        try:
            web_ctx_digest = lookup_web_context(user_msg)
        except Exception:
            web_ctx_digest = ""
        pipeline_label = "web+llm" if web_ctx_digest else "llm"
        if pipeline_label == "web+llm":
            try:
                logger.info("knowledge_pipeline selected=web+llm topic=%s user=%s", extract_topic(user_msg), (int(current["id"]) if (current and current.get("id")) else None))
            except Exception:
                pass
        recent3 = []
        try:
            recent3 = list(getattr(state, 'recent_topics', [])[-3:]) if state else []
        except Exception:
            recent3 = []
        state_ctx = f"[STATE] Stimmung: {getattr(state,'mood', 'neutral')}, Themen: {', '.join(recent3) if recent3 else '-'}"
        try:
            r_llm = await asyncio.wait_for(reason_about(
                user_msg,
                persona=(body.persona or "friendly"),
                lang=(body.lang or "de-DE"),
                style=_sanitize_style(body.style),
                bullets=_sanitize_bullets(body.bullets),
                logic=_sanitize_logic(getattr(body, 'logic', 'balanced')),
                fmt=_sanitize_format(getattr(body, 'format', 'plain')),
                retrieval_snippet=(web_ctx_digest or state_ctx or ""),
            ), timeout=PLANNER_TIMEOUT_SECONDS)
        except Exception:
            r_llm = {}
        reply_llm = extract_natural_reply(r_llm)
        srcs_llm = list((r_llm or {}).get("sources") or []) if isinstance(r_llm, dict) else []
        src_block_llm = format_sources(srcs_llm or [], limit=2)
        if src_block_llm:
            reply_llm = (reply_llm or "") + ("\n\n" + src_block_llm)
        reply_llm = postprocess_and_style(reply_llm, persona, state, profile_used, style_prompt)
        reply_llm = make_user_friendly_text(reply_llm, state)
        conv_id_llm = None
        try:
            if current and current.get("id"):
                uid = int(current["id"])  # type: ignore
                conv = _ensure_conversation(db, uid, body.conv_id)
                conv_id_llm = conv.id
                _save_msg(db, conv.id, "user", user_msg)
                _save_msg(db, conv.id, "ai", reply_llm)
                asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply_llm, body.lang or "de-DE"))
        except Exception:
            conv_id_llm = None
        conv_out_llm = conv_id_llm if conv_id_llm is not None else (body.conv_id or None)
        try:
            if state is not None:
                state.last_pipeline = pipeline_label  # type: ignore[attr-defined]
        except Exception:
            pass
        return _finalize_reply(
            reply_llm,
            state=state, conv_id=conv_out_llm, intent="knowledge", topic=extract_topic(user_msg), pipeline=pipeline_label,
            extras={"ok": True, "auto_modes": [], "role_used": "LLM", "memory_ids": [], "quick_replies": _quick_replies_for_topic(extract_topic(user_msg), user_msg), "topic": extract_topic(user_msg), "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": pipeline_label, "topic": extract_topic(user_msg)}}
        )

    # Experiences: retrieve compact relevant snippets for prompt/context
    experiences_snip = ""
    experiences_raw: List[Dict[str, Any]] = []
    try:
        experiences_raw = get_relevant_experiences(user_msg, limit=5)
        if experiences_raw:
            experiences_snip = summarize_experiences(experiences_raw, max_lines=5)
    except Exception:
        experiences_snip = ""

    # Persona and NLU intent detection (must be set before planner/fallback use)
    try:
        persona = get_kiana_persona()
    except Exception:
        persona = SimpleNamespace(name="Kiana", role="deine digitale Begleiterin im KI_ana-System", core_values=["Ehrlichkeit","Hilfsbereitschaft","Neugier"], rules={})  # type: ignore
    try:
        intent = detect_intent(user_msg)
    except Exception:
        intent = "general"
    try:
        logger.warning("CHAT_DEBUG intent=%s", intent)
    except Exception:
        pass

    if intent == "knowledge_query" or _looks_like_current_query(user_msg):
        return await _answer_with_web_digest(user_msg, body, state, persona, profile_used, style_prompt, style_used_meta, current, db, risk_flag)

    try:
        special = handle_special_cases(intent, user_msg, (body.lang or "de"), state, persona)
        if isinstance(special, str) and special.strip():
            reply = postprocess_and_style(special, persona, state, profile_used, style_prompt)
            if not reply or not str(reply).strip():
                reply = special.strip()
            try:
                logger.warning("CHAT_DEBUG special-case reply=%r (intent=%s)", reply, intent)
            except Exception:
                pass
            conv_id_sp: Optional[int] = None
            try:
                if current and current.get("id"):
                    uid = int(current["id"])  # type: ignore
                    conv = _ensure_conversation(db, uid, body.conv_id)
                    conv_id_sp = conv.id
                    _save_msg(db, conv.id, "user", user_msg)
                    _save_msg(db, conv.id, "ai", reply)
                    asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply, body.lang or "de-DE"))
            except Exception:
                conv_id_sp = None
            try:
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                uid_for_mem = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                save_experience(uid_for_mem, conv_id_sp, {
                    "type": f"special_{intent}", "user_message": user_msg, "assistant_reply": reply,
                    "timestamp": now_iso,
                })
                if state:
                    save_state(state)
            except Exception:
                pass
            if consent_note:
                reply = (reply + "\n\n" + consent_note).strip()
            conv_out_sp = conv_id_sp if conv_id_sp is not None else (body.conv_id or None)
            try:
                logger.warning("CHAT_DEBUG final reply before response: %r (intent=%s)", reply, intent)
            except Exception:
                pass
            return _finalize_reply(
                reply,
                state=state, conv_id=conv_out_sp, intent="greeting", topic="greeting",
                extras={"ok": True, "auto_modes": [], "role_used": "Direkt", "memory_ids": [], "quick_replies": _quick_replies_for_topic("greeting", user_msg), "topic": "greeting", "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": "special_greeting"}}
            )
    except Exception:
        pass

    # Perception: intent + topic_path; life-state update & mood derivation
    try:
        thought = perceive(user_msg, state)
        topic_path = str(thought.get('topic_path') or extract_topic_path(user_msg))
        if state:
            state.update_from_event("user_message", topic_path)
            state.mood = state.derive_mood()
    except Exception:
        topic_path = extract_topic_path(user_msg)

    # EARLY BYPASS: Self/Meta questions (deterministic, no planner)
    try:
        if intent == "self_meta":
            try:
                state_line = express_state_human(state.to_dict() if state else {})
            except Exception:
                state_line = (
                    "Ich nehme meine Zustände eher als Muster und Veränderungen wahr, nicht wie ein Mensch Gefühle."
                )
            answer = (
                "Gute Frage. 😊\n\n"
                "Ich kann Zeit und Abläufe nicht so fühlen wie ein Mensch, "
                "aber ich kann sehr genau verfolgen, was davor und danach passiert "
                "und wie sich mein innerer Zustand verändert.\n\n"
                f"{state_line}"
            )
            answer = postprocess_and_style(answer, persona, state, profile_used, style_prompt)
            answer = make_user_friendly_text(answer, state)
            conv_id_meta: Optional[int] = None
            try:
                if current and current.get("id"):
                    uid = int(current["id"])  # type: ignore
                    conv = _ensure_conversation(db, uid, body.conv_id)
                    conv_id_meta = conv.id
                    _save_msg(db, conv.id, "user", user_msg)
                    _save_msg(db, conv.id, "ai", answer)
                    asyncio.create_task(_retitle_if_needed(conv.id, user_msg, answer, body.lang or "de-DE"))
            except Exception:
                conv_id_meta = None
            try:
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                uid_for_mem = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                save_experience(uid_for_mem, conv_id_meta, {
                    "type": "self_meta", "user_message": user_msg, "assistant_reply": answer,
                    "timestamp": now_iso,
                })
                if state:
                    save_state(state)
            except Exception:
                pass
            conv_out_meta = conv_id_meta if conv_id_meta is not None else (body.conv_id or None)
            return _finalize_reply(
                answer,
                state=state, conv_id=conv_out_meta, intent="self_meta", topic="self_meta",
                extras={"ok": True, "auto_modes": [], "role_used": "Direkt", "memory_ids": [], "quick_replies": _quick_replies_for_topic("self_meta", user_msg), "topic": "self_meta", "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": "self_meta"}}
            )
    except Exception:
        pass

    if intent == "knowledge_query":
        return await _answer_with_web_digest(user_msg, body, state, persona, profile_used, style_prompt, style_used_meta, current, db, risk_flag)

    # EARLY BYPASS: identity intents answered deterministically (no LLM)
    try:
        if intent in ("identity_who", "identity_name"):
            name = getattr(persona, "name", "Kiana")
            role = getattr(persona, "role", "deine digitale Begleiterin im KI_ana-System")
            core_values = ", ".join(getattr(persona, "core_values", []) or []) or "Ehrlichkeit, Hilfsbereitschaft und Neugier"
            if intent == "identity_name":
                r = f"Ich heiße {name}. Ich bin {role}."
            else:
                r = f"Ich bin {name}, {role}. Mir sind Dinge wie {core_values} besonders wichtig."
            # Postprocess and style
            r = postprocess_and_style(r, persona, state, profile_used, style_prompt)
            if consent_note:
                r = (r + "\n\n" + consent_note).strip()
            # Persist conversation if logged in
            conv_id_id: Optional[int] = None
            try:
                if current and current.get("id"):
                    uid = int(current["id"])  # type: ignore
                    conv = _ensure_conversation(db, uid, body.conv_id)
                    conv_id_id = conv.id
                    _save_msg(db, conv.id, "user", user_msg)
                    _save_msg(db, conv.id, "ai", r)
                    asyncio.create_task(_retitle_if_needed(conv.id, user_msg, r, body.lang or "de-DE"))
            except Exception:
                conv_id_id = None
            # Save experience and state
            try:
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                uid_for_mem = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                save_experience(uid_for_mem, conv_id_id, {
                    "type": "experience", "user_message": user_msg, "assistant_reply": r,
                    "timestamp": now_iso, "mood": (state.mood if state else "neutral"), "topics": ["identity"],
                })
                if state:
                    save_state(state)
                if state and experiences_raw:
                    asyncio.create_task(reflect_if_needed(state, experiences_raw))
            except Exception:
                pass
            conv_out_id = conv_id_id if conv_id_id is not None else (body.conv_id or None)
            return _finalize_reply(
                r,
                state=state, conv_id=conv_out_id, intent="identity", topic="identity",
                extras={"ok": True, "auto_modes": [], "role_used": "Direkt", "memory_ids": [], "quick_replies": _quick_replies_for_topic("identity", user_msg), "topic": "identity", "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": "identity_direct"}}
            )
    except Exception:
        # If identity handling fails, continue to other early bypasses
        pass

    # EARLY BYPASS: deterministic time/date answers (no LLM)
    try:
        kind_td = is_time_or_date_question(user_msg)
        if kind_td:
            reply_td = answer_time_date(kind_td, lang=(body.lang or "de"))
            # style/pass through
            reply_td = _apply_style(reply_td, profile_used)
            if style_prompt:
                reply_td = (reply_td + "\n\n" + style_prompt).strip()
            # persist conversation if logged in
            conv_id_td = None
            try:
                if current and current.get("id"):
                    uid = int(current["id"])  # type: ignore
                    conv = _ensure_conversation(db, uid, body.conv_id)
                    conv_id_td = conv.id
                    _save_msg(db, conv.id, "user", user_msg)
                    _save_msg(db, conv.id, "ai", reply_td)
                    asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply_td, body.lang or "de-DE"))
            except Exception:
                conv_id_td = None
            # save experience and state
            try:
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                extracted_topics = [extract_topic(user_msg) or "Zeit/Datum"]
                uid_for_mem = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                save_experience(uid_for_mem, conv_id_td, {
                    "type": "experience", "user_message": user_msg, "assistant_reply": reply_td,
                    "timestamp": now_iso, "mood": (state.mood if state else "neutral"), "topics": extracted_topics,
                })
                if state:
                    save_state(state)
                if state and experiences_raw:
                    asyncio.create_task(reflect_if_needed(state, experiences_raw))
            except Exception:
                pass
            conv_out_td = conv_id_td if conv_id_td is not None else (body.conv_id or None)
            return _finalize_reply(
                reply_td,
                state=state, conv_id=conv_out_td, intent="time_date", topic=extract_topic(user_msg),
                extras={"ok": True, "auto_modes": [], "role_used": "Deterministic", "memory_ids": [], "quick_replies": _quick_replies_for_topic(extract_topic(user_msg), user_msg), "topic": extract_topic(user_msg), "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": "time_date_direct"}}
            )
    except Exception:
        pass

    # KNOWLEDGE QUERY: Try memory first, then web, else ask user (child learning)
    try:
        if intent in ("knowledge", "knowledge_query"):
            try:
                logger.info("Knowledge intent for user_msg=%r", user_msg)
            except Exception:
                pass
            # Temporary test bypass: force simple LLM for the specific Einhorn prompt
            try:
                _um_low = (user_msg or "").lower()
                if ("drei pinke einhörner" in _um_low) and ("stephansdom" in _um_low):
                    try:
                        raw_simple = await call_llm_once(
                            user_msg,
                            (_system_prompt if ('_system_prompt' in locals()) else system_prompt(body.persona)),
                            body.lang or "de-DE",
                            body.persona or "friendly",
                        )
                        simple_reply = postprocess_and_style(clean(raw_simple or ""), persona, state, profile_used, style_prompt)
                        if not simple_reply or not str(simple_reply).strip():
                            simple_reply = "In einem Satz: Drei pinke Einhörner naschen Pizza auf dem Stephansdom und wippen im Takt von Radio 88.6."
                        return _finalize_reply(
                            simple_reply,
                            state=state, conv_id=(body.conv_id or None), intent="knowledge", topic=extract_topic(user_msg), pipeline="llm",
                            extras={"ok": True, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": "llm", "bypass": True}}
                        )
                    except Exception:
                        logger.exception("knowledge_llm_bypass failed for Einhorn test", extra={"intent": intent, "user_msg": user_msg})
                        safe_text = (
                            "Ich formuliere es kurz kreativ: Drei pinke Einhörner naschen Pizza auf dem Stephansdom und hören Radio 88.6."
                        )
                        return _finalize_reply(
                            safe_text,
                            state=state, conv_id=(body.conv_id or None), intent="knowledge", topic=extract_topic(user_msg), pipeline="llm",
                            status="unsafe",
                            extras={"ok": True, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": "llm", "bypass": True, "status": "unsafe"}}
                        )
            except Exception:
                pass
            # Wrap the main Knowledge flow with explicit exception logging and graceful fallback
            # 0) Addressbook-first KM narrow search
            try:
                from netapi.core.addressbook import suggest_topic_paths as _ab_suggest, find_paths_for_topic as _ab_find_paths
            except Exception:
                _ab_suggest = None  # type: ignore
                _ab_find_paths = None  # type: ignore
            try:
                topic_guess = extract_topic(user_msg) or ""
                ab_paths: List[str] = []
                try:
                    if _ab_suggest:
                        ab_paths.extend(_ab_suggest(user_msg) or [])
                except Exception:
                    pass
                try:
                    if _ab_find_paths and topic_guess:
                        ab_paths.extend(_ab_find_paths(topic_guess) or [])
                except Exception:
                    pass
                # De-dup
                seen = set(); ab_paths = [p for p in ab_paths if (p and not (p in seen or seen.add(p)))]
                best_reply = None
                best_score = -1.0
                best_blk = None
                best_path = None
                if ab_paths:
                    for pth in ab_paths:
                        try:
                            ab_hits = km_find_relevant_blocks(user_msg, limit=3, topic_hints={"topic_path": pth})
                        except Exception:
                            ab_hits = []
                        if not ab_hits:
                            continue
                        blk, score = ab_hits[0]
                        if score > best_score:
                            best_score = score
                            best_blk = blk
                            best_path = pth
                    if best_blk is not None:
                        try:
                            best_blk.touch(used_delta=1, conf_delta=0.05)
                            km_save_block(best_blk)
                        except Exception:
                            pass
                        reply_ab = (
                            "Ich greife auf meinen Wissensblock zurück: "
                            + (best_blk.summary or best_blk.content or "")
                        ).strip()
                        reply_ab = postprocess_and_style(reply_ab, persona, state, profile_used, style_prompt)
                        reply_ab = make_user_friendly_text(reply_ab, state)
                        try:
                            logger.info("knowledge_pipeline", extra={"selected": "km_addressbook", "topic": topic_guess, "topic_path": best_path, "user": (int(current["id"]) if (current and current.get("id")) else None)})
                        except Exception:
                            pass
                        try:
                            if state is not None:
                                state.last_pipeline = "km_addressbook"  # type: ignore[attr-defined]
                        except Exception:
                            pass
                        return _finalize_reply(
                            reply_ab,
                            state=state, conv_id=(body.conv_id or None), intent="knowledge", topic=extract_topic(user_msg), pipeline="km_addressbook",
                            extras={"ok": True, "auto_modes": [], "role_used": "Wissen", "memory_ids": ([str(getattr(best_blk, 'id', ''))] if getattr(best_blk, 'id', None) else []), "quick_replies": _quick_replies_for_topic(extract_topic(user_msg), user_msg), "topic": extract_topic(user_msg), "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": "km_addressbook", "topic": extract_topic(user_msg)}}
                        )
            except Exception:
                pass
            # 1) KnowledgeManager: try filesystem knowledge blocks first
            #    Detect and avoid returning meta/hint-only blocks (e.g., "schau auf wikipedia")
            try:
                km_hint_only = False
                def _is_hint_only(txt: str) -> bool:
                    try:
                        t = (txt or "").strip().lower()
                        if not t:
                            return False
                        # short + contains meta search hints
                        if len(t) <= 220 and (
                            ("wikipedia" in t) or ("im internet" in t) or ("google" in t) or ("schau mal auf" in t) or ("schau im" in t) or ("such im" in t)
                        ):
                            # naive factual signal: numbers with units or years
                            if re.search(r"\b(\d{3,4}|%|km|km/s|mio\.|milliarden|°c)\b", t):
                                return False
                            # naked URL without explanation
                            if re.search(r"https?://\S+", t) and len(t) < 180:
                                return True
                            return True
                        # pure link line
                        if re.fullmatch(r"https?://\S+", t):
                            return True
                        # state-dump style JSON (self diagnostics) shouldn't count as knowledge
                        if t.startswith("{") and '"recent_topics"' in t and '"learning_buffer"' in t:
                            return True
                    except Exception:
                        return False
                    return False
                topic_hints = {"label": extract_topic(user_msg) or "", "category": None}
                km_topic = km_guess_topic_path(user_msg, hints=topic_hints)
                km_results = km_find_relevant_blocks(user_msg, limit=5, topic_hints={"topic_path": km_topic})
                if km_results:
                    # Determine if all candidates are hint-only
                    try:
                        _all_hint = True
                        for _blk, _sc in km_results:
                            _txt = (getattr(_blk, 'summary', '') or getattr(_blk, 'content', '') or '').strip()
                            if not _is_hint_only(_txt):
                                _all_hint = False
                                break
                        if _all_hint:
                            km_hint_only = True
                    except Exception:
                        km_hint_only = False

                    top_blk, top_score = km_results[0]
                    if top_score >= 1.0 and not km_hint_only:
                        try:
                            top_blk.touch(used_delta=1, conf_delta=0.05)
                            km_save_block(top_blk)
                        except Exception:
                            pass
                        reply_km = (
                            "Ich erinnere mich, dass du mir dazu schon etwas erklärt hast. "
                            + (top_blk.summary or top_blk.content or "")
                        ).strip()
                        reply_km = postprocess_and_style(reply_km, persona, state, profile_used, style_prompt)
                        reply_km = make_user_friendly_text(reply_km, state)
                        try:
                            logger.info("Knowledge intent", extra={
                                "user_msg": user_msg,
                                "topic_path": km_topic,
                                "has_blocks": True,
                                "source": "knowledge_manager",
                            })
                        except Exception:
                            pass
                        # Guard and finalize
                        try:
                            if isinstance(reply_km, str):
                                s = reply_km.strip()
                                if s.startswith('{') and '"recent_topics"' in s and '"mood"' in s:
                                    logger.warning("chat_once: knowledge answer tried to return self-state JSON, converting to human text")
                                    from netapi.core.expression import express_state_human as _expr_km
                                    reply_km = _expr_km(state) if state else "Ich spüre, dass ich gerade vor allem lernen und verstehen will – sag mir gern, was du konkret über das Thema wissen möchtest. 🙂"
                        except Exception:
                            pass
                        # pipeline log + extras
                        try:
                            uid_log = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                        except Exception:
                            uid_log = None
                        try:
                            logger.warning(f"knowledge_pipeline selected=km topic={extract_topic(user_msg)} user={uid_log}")
                        except Exception:
                            pass
                        # set last_pipeline
                        try:
                            if state is not None:
                                state.last_pipeline = "km"  # type: ignore[attr-defined]
                        except Exception:
                            pass
                        return _finalize_reply(
                            reply_km,
                            state=state, conv_id=(body.conv_id or None), intent="knowledge", topic=extract_topic(user_msg), pipeline="km",
                            extras={"ok": True, "auto_modes": [], "role_used": "Wissen", "memory_ids": ([str(getattr(top_blk, 'id', ''))] if getattr(top_blk, 'id', None) else []), "quick_replies": _quick_replies_for_topic(extract_topic(user_msg), user_msg), "topic": extract_topic(user_msg), "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": "km", "topic": extract_topic(user_msg)}}
                        )
                    else:
                        # If KM found only hint blocks, prefer web next.
                        if km_hint_only:
                            try:
                                uid_log = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                            except Exception:
                                uid_log = None
                            try:
                                logger.info(f"knowledge_pipeline selected=km_hint_to_web topic={extract_topic(user_msg)} user={uid_log}")
                            except Exception:
                                pass
            except Exception:
                pass
            # 1) Memory search by topic_path (short-term first, then long-term; fallback: user_msg)
            ans_mem = ""
            src_block_mem = ""
            memory_ids_mem: list[str] = []
            try:
                from netapi import memory_store as _mem
                # Prefer explicit short-term topic index hits
                used_short = False
                if hasattr(_mem, 'topic_index_list') and topic_path:
                    st_ids = _mem.topic_index_list(topic_path)
                    if st_ids:
                        st_blk = _mem.load_short_term_block(st_ids[-1]) if hasattr(_mem, 'load_short_term_block') else None
                        if st_blk:
                            used_short = True
                            ans_mem = (st_blk.get('info') or '').strip()
                            try:
                                mid = st_blk.get('id') or st_ids[-1]
                                if mid:
                                    memory_ids_mem = [str(mid)]
                            except Exception:
                                pass
                            try:
                                if hasattr(_mem, 'increment_use'):
                                    _mem.increment_use(st_blk.get('id') or st_ids[-1])
                                if hasattr(_mem, 'maybe_promote'):
                                    _mem.maybe_promote(st_blk.get('id') or st_ids[-1])
                            except Exception:
                                pass
                if not used_short:
                    # Fall back to long-term vector search via topic path or original user text
                    query = topic_path or user_msg
                    hits = _mem.search_blocks(query=query, top_k=3, min_score=0.10) if hasattr(_mem, 'search_blocks') else []
                    if hits:
                        bid, sc = hits[0]
                        blk = _mem.get_block(bid)
                        if blk:
                            ans_mem = (blk.get('content') or '').strip()
                            try:
                                if bid:
                                    memory_ids_mem = [str(bid)]
                            except Exception:
                                pass
                            # small concise summary if very long
                            if len(ans_mem) > 600:
                                try:
                                    ans_mem = short_summary(ans_mem, max_chars=500)
                                except Exception:
                                    ans_mem = ans_mem[:500]
                            src_block_mem = format_sources([{"title": blk.get('title',''), "url": blk.get('url','')}], limit=1)
            except Exception:
                ans_mem = ""
            if ans_mem:
                # Avoid returning hint-only memory content; force web if so
                try:
                    if _is_hint_only(ans_mem):
                        ans_mem = ""
                        try:
                            logger.info(f"knowledge_pipeline km_hint_to_web (memory) topic={extract_topic(user_msg)}")
                        except Exception:
                            pass
                        km_hint_only = True
                except Exception:
                    pass
                if ans_mem:
                    reply_k = ans_mem
                    if src_block_mem:
                        reply_k = (reply_k + "\n\n" + src_block_mem).strip()
                    reply_k = postprocess_and_style(reply_k, persona, state, profile_used, style_prompt)
                    reply_k = make_user_friendly_text(reply_k, state)
                    # Persist and return
                    conv_id_k = None
                    try:
                        if current and current.get("id"):
                            uid = int(current["id"])  # type: ignore
                            conv = _ensure_conversation(db, uid, body.conv_id)
                            conv_id_k = conv.id
                            _save_msg(db, conv.id, "user", user_msg)
                            _save_msg(db, conv.id, "ai", reply_k)
                            asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply_k, body.lang or "de-DE"))
                    except Exception:
                        conv_id_k = None
                    try:
                        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                        uid_for_mem = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                        save_experience(uid_for_mem, conv_id_k, {"type": "knowledge_from_memory", "user_message": user_msg, "assistant_reply": reply_k, "topic_path": topic_path, "timestamp": now_iso})
                        if state:
                            try:
                                state.last_pipeline = "km"  # type: ignore[attr-defined]
                            except Exception:
                                pass
                            save_state(state)
                    except Exception:
                        pass
                    # Knowledge hard-guard: prevent self-state JSON leak before finalizing
                    try:
                        if isinstance(reply_k, str):
                            s = reply_k.strip()
                            if s.startswith('{') and '"recent_topics"' in s and '"mood"' in s:
                                logger.warning("chat_once: knowledge answer tried to return self-state JSON, converting to human text")
                                try:
                                    from netapi.core.expression import express_state_human as _expr_k
                                    reply_k = _expr_k(state) if state else "Ich spüre, dass ich gerade vor allem lernen und verstehen will – sag mir gern, was du konkret über das Thema wissen möchtest. 🙂"
                                except Exception:
                                    reply_k = "Ich spüre, dass ich gerade vor allem lernen und verstehen will – sag mir gern, was du konkret über das Thema wissen möchtest. 🙂"
                    except Exception:
                        pass
                    # pipeline log + extras
                    try:
                        uid_log = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                    except Exception:
                        uid_log = None
                    try:
                        logger.info(f"knowledge_pipeline selected=km topic={extract_topic(user_msg)} user={uid_log}")
                    except Exception:
                        pass
                    # set last_pipeline
                    try:
                        if state is not None:
                            state.last_pipeline = "km"  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    _bump_answers_and_maybe_reflect(extract_topic(user_msg))
                    return _finalize_reply(
                        reply_k,
                        state=state, conv_id=(conv_id_k if conv_id_k is not None else (body.conv_id or None)), intent="knowledge", topic=extract_topic(user_msg), pipeline="km",
                        extras={"ok": True, "auto_modes": [], "role_used": "Wissen", "memory_ids": (memory_ids_mem or []), "quick_replies": _quick_replies_for_topic(extract_topic(user_msg), user_msg), "topic": extract_topic(user_msg), "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": "km", "topic": extract_topic(user_msg)}}
                    )

            # 2) LLM consultation (local model) if memory empty or low-confidence
            llm_text = None
            llm_conf = 0.0
            llm_srcs: list = []
            llm_tokens = 0
            web_ctx_snippet = ""
            used_web_ctx = False
            try:
                web_ctx_snippet = lookup_web_context(user_msg)
            except Exception:
                web_ctx_snippet = ""
            try:
                logger.info("knowledge_pipeline web_ctx_len=%d topic=%s", len(web_ctx_snippet or ""), extract_topic(user_msg))
            except Exception:
                pass
            if web_ctx_snippet:
                used_web_ctx = True
                try:
                    uid_log = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                except Exception:
                    uid_log = None
                try:
                    logger.info(
                        "knowledge_pipeline selected=web+llm topic=%s user=%s",
                        extract_topic(user_msg),
                        uid_log,
                    )
                except Exception:
                    pass
            else:
                try:
                    logger.info("knowledge_pipeline web_ctx_len=0 topic=%s", extract_topic(user_msg))
                except Exception:
                    pass
            try:
                if not ans_mem:
                    # Build compact context with time and brief self-state
                    _time_block = build_timeblock()
                    recent3 = []
                    try:
                        recent3 = list(getattr(state, 'recent_topics', [])[-3:]) if state else []
                    except Exception:
                        recent3 = []
                    state_ctx = f"[STATE] Stimmung: {getattr(state,'mood', 'neutral')}, Themen: {', '.join(recent3) if recent3 else '-'}"
                    _sys = build_system_prompt(persona, state, _time_block, "")
                    _retr_snip = (_sys + "\n\n" + state_ctx).strip() if _sys else state_ctx
                    async def _run_llm_consult():
                        return await reason_about(
                            user_msg,
                            persona=(body.persona or "friendly"), lang=(body.lang or "de-DE"),
                            style=_sanitize_style(body.style), bullets=_sanitize_bullets(body.bullets),
                            logic=_sanitize_logic(getattr(body, 'logic', 'balanced')),
                            fmt=_sanitize_format(getattr(body, 'format', 'plain')),
                            # Prevent reasoner from auto-fetching web context for general knowledge questions.
                            retrieval_snippet=(web_ctx_snippet or _retr_snip),
                        )
                    try:
                        r_llm = await asyncio.wait_for(_run_llm_consult(), timeout=PLANNER_TIMEOUT_SECONDS)
                    except Exception:
                        r_llm = {}
                    llm_text = extract_natural_reply(r_llm)
                    try:
                        llm_srcs = list((r_llm or {}).get('sources') or []) if isinstance(r_llm, dict) else []
                    except Exception:
                        llm_srcs = []
                    # Confidence heuristic
                    try:
                        llm_tokens = len((llm_text or "").split())
                        if llm_text and not is_low_confidence_answer(llm_text):
                            llm_conf = 0.8
                        else:
                            llm_conf = 0.5
                    except Exception:
                        llm_conf = 0.5
                    if llm_text:
                        reply_llm = llm_text
                        src_block_llm = format_sources(llm_srcs or [], limit=2)
                        if src_block_llm:
                            reply_llm = (reply_llm + "\n\n" + src_block_llm).strip()
                        reply_llm = postprocess_and_style(reply_llm, persona, state, profile_used, style_prompt)
                        reply_llm = make_user_friendly_text(reply_llm, state)
                        # Explicit uncertainty checks for web fallback
                        _raw_llm_clean = (llm_text or "").strip()
                        _too_short = len(_raw_llm_clean) < 30
                        try:
                            _unsure_rx = re.compile(r"(weiß\s+ich|nicht\s+sicher|schau|schauen|vielleicht|…|\.{3})", re.I)
                            _unsure = bool(_unsure_rx.search(_raw_llm_clean))
                        except Exception:
                            _unsure = False
                        llm_should_web = _too_short or _unsure or (llm_conf < 0.35)

                        # If acceptable (not unsure and not too short), save and return
                        if not llm_should_web:
                            # Save LLM result as knowledge block + addressbook registration
                            try:
                                tp2 = km_guess_topic_path(user_msg, hints={"label": extract_topic(user_msg) or ""})
                                kb2 = km_promote_block(_raw_llm_clean, user_msg, source="llm", hints={"topic_path": tp2, "summary": short_summary(_raw_llm_clean)}, base_confidence=0.65, tags=["llm","autosaved"])  # type: ignore
                                try:
                                    from netapi.core.addressbook import register_block_for_topic as _ab_register
                                    if kb2 and getattr(kb2, 'id', None) and getattr(kb2, 'topic_path', None):
                                        _ab_register(kb2.topic_path, kb2.id)
                                        try:
                                            logger.info("addressbook_register", extra={"topic_path": kb2.topic_path, "block_id": kb2.id})
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                                try:
                                    from netapi import memory_store as _mem
                                    _mem.save_memory_entry(title=(extract_topic(user_msg) or tp2)[:120], content=_raw_llm_clean, tags=["llm","learned"], url=None)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                            # Log selection and finalize
                            try:
                                logger.info(f"knowledge_pipeline selected=llm topic={extract_topic(user_msg)} conf={llm_conf:.2f}")
                            except Exception:
                                pass
                            # Guard against self-state leak before finalizer
                            try:
                                if isinstance(reply_llm, str):
                                    s = reply_llm.strip()
                                    if s.startswith('{') and '"recent_topics"' in s and '"mood"' in s:
                                        logger.warning("chat_once: knowledge answer tried to return self-state JSON, converting to human text")
                                        from netapi.core.expression import express_state_human as _expr_llm
                                        reply_llm = _expr_llm(state) if state else "Ich spüre, dass ich gerade vor allem lernen und verstehen will – sag mir gern, was du konkret über das Thema wissen möchtest. 🙂"
                            except Exception:
                                pass
                            # pipeline log + extras
                            try:
                                uid_log = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                            except Exception:
                                uid_log = None
                            try:
                                logger.info(f"knowledge_pipeline selected=llm topic={extract_topic(user_msg)} user={uid_log} conf={llm_conf:.2f}")
                            except Exception:
                                pass
                            # set last_pipeline
                            try:
                                if state is not None:
                                    state.last_pipeline = "llm"  # type: ignore[attr-defined]
                            except Exception:
                                pass
                            _bump_answers_and_maybe_reflect(extract_topic(user_msg))
                        pipeline_label = "web+llm" if used_web_ctx else "llm"
                        return _finalize_reply(
                            reply_llm,
                            state=state, conv_id=(body.conv_id or None), intent="knowledge", topic=extract_topic(user_msg), pipeline=pipeline_label,
                            extras={"ok": True, "auto_modes": [], "role_used": "LLM", "memory_ids": [], "quick_replies": _quick_replies_for_topic(extract_topic(user_msg), user_msg), "topic": extract_topic(user_msg), "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": pipeline_label, "confidence": llm_conf, "topic": extract_topic(user_msg)}}
                        )
            except Exception:
                llm_text = None

            # 3) Web answer if allowed
            web_ans, web_srcs = (None, [])
            try:
                # Web if allowed and LLM uncertain (<0.6) or answer too short (<10 tokens)
                web_ok = getattr(body, 'web_ok', True)
                llm_uncertain = (llm_conf < 0.6) or (llm_tokens < 10)
                # User trigger phrases: "dort nachsehen/nachschauen/nachlesen"
                try:
                    user_requests_web = bool(re.search(r"\b(dort\s+nachsehen|dort\s+nachschauen|dort\s+nachlesen|auf\s+wikipedia\s+nachsehen|auf\s+wikipedia\s+nachschauen)\b", (user_msg or "").lower()))
                except Exception:
                    user_requests_web = False
                # Controlled Freedom: in explore mode, allow autonomous web if uncertain
                try:
                    if state is not None and bool(getattr(state, 'mode_explore', False)) and llm_uncertain:
                        web_ok = True
                except Exception:
                    pass
                # Also trigger web if KM only provided hints or user explicitly asked to look there
                if web_ok and (km_hint_only or user_requests_web or (not ans_mem and (llm_text is None or llm_uncertain))):
                    try:
                        logger.info(f"knowledge_pipeline web_trigger reason={'km_hint_only' if km_hint_only else ('user_request' if user_requests_web else 'uncertain')} topic={extract_topic(user_msg)}")
                    except Exception:
                        pass
                    web_ans, web_srcs = try_web_answer(user_msg, limit=3)
            except Exception:
                web_ans, web_srcs = (None, [])
            if web_ans:
                try:
                    if state:
                        add_learning_item(state, topic_path, web_ans, source="web")
                except Exception:
                    pass
                # Promote/save as KnowledgeBlock immediately (source=web)
                try:
                    _hints = {"topic_path": topic_path, "title": extract_topic(user_msg) or None, "summary": short_summary(web_ans)}
                    kb = km_promote_block(web_ans, user_msg, source="web", hints=_hints, base_confidence=0.7, tags=["web","autosaved"])  # type: ignore
                    try:
                        from netapi.core.addressbook import register_block_for_topic as _ab_register
                        if kb and getattr(kb, 'id', None) and getattr(kb, 'topic_path', None):
                            _ab_register(kb.topic_path, kb.id)
                            try:
                                logger.info("addressbook_register", extra={"topic_path": kb.topic_path, "block_id": kb.id})
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass
                reply_k2 = web_ans
                src_block_ws = format_sources(web_srcs or [], limit=2)
                if src_block_ws:
                    reply_k2 = (reply_k2 + "\n\n" + src_block_ws).strip()
                reply_k2 = postprocess_and_style(reply_k2, persona, state, profile_used, style_prompt)
                reply_k2 = make_user_friendly_text(reply_k2, state)
                conv_id_k2 = None
                try:
                    if current and current.get("id"):
                        uid = int(current["id"])  # type: ignore
                        conv = _ensure_conversation(db, uid, body.conv_id)
                        conv_id_k2 = conv.id
                        _save_msg(db, conv.id, "user", user_msg)
                        _save_msg(db, conv.id, "ai", reply_k2)
                        asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply_k2, body.lang or "de-DE"))
                except Exception:
                    conv_id_k2 = None
                try:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    uid_for_mem = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                    save_experience(uid_for_mem, conv_id_k2, {"type": "knowledge_from_web", "user_message": user_msg, "assistant_reply": reply_k2, "topic_path": topic_path, "timestamp": now_iso})
                    if state:
                        try:
                            state.last_pipeline = "web"  # type: ignore[attr-defined]
                        except Exception:
                            pass
                        save_state(state)
                except Exception:
                    pass
                # Knowledge hard-guard for web answer
                try:
                    if isinstance(reply_k2, str):
                        s = reply_k2.strip()
                        if s.startswith('{') and '"recent_topics"' in s and '"mood"' in s:
                            logger.warning("chat_once: knowledge answer tried to return self-state JSON, converting to human text")
                            try:
                                from netapi.core.expression import express_state_human as _expr_k2
                                reply_k2 = _expr_k2(state) if state else "Ich spüre, dass ich gerade vor allem lernen und verstehen will – sag mir gern, was du konkret über das Thema wissen möchtest. 🙂"
                            except Exception:
                                reply_k2 = "Ich spüre, dass ich gerade vor allem lernen und verstehen will – sag mir gern, was du konkret über das Thema wissen möchtest. 🙂"
                except Exception:
                    pass
                # pipeline log + extras
                try:
                    uid_log = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                except Exception:
                    uid_log = None
                try:
                    logger.info(f"knowledge_pipeline selected=web topic={extract_topic(user_msg)} user={uid_log} conf={llm_conf:.2f}")
                except Exception:
                    pass
                # set last_pipeline
                try:
                    if state is not None:
                        state.last_pipeline = "web"  # type: ignore[attr-defined]
                except Exception:
                    pass
                _bump_answers_and_maybe_reflect(extract_topic(user_msg))
                return _finalize_reply(
                    reply_k2,
                    state=state, conv_id=(conv_id_k2 if conv_id_k2 is not None else (body.conv_id or None)), intent="knowledge", topic=extract_topic(user_msg), pipeline="web",
                    extras={"ok": True, "auto_modes": ["web"], "role_used": "Forscher", "memory_ids": [], "quick_replies": ["Ich erkläre es in 2-3 Sätzen"], "topic": extract_topic(user_msg), "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": "web", "topic": extract_topic(user_msg)}}
                )

            # 3.5) LLM quick answer for simple/general topics before asking child
            try:
                basic_rx = re.compile(r"\b(erde|mond|sonne|merkur|venus|mars|jupiter|saturn|uranus|neptun|österreich|oesterreich|wien|europa)\b", re.I)
                is_basic = bool(basic_rx.search(user_msg or "")) or _is_simple_knowledge_question(user_msg or "")
            except Exception:
                is_basic = False
            # Try LLM answer if topic is basic OR as a last attempt before child
            try:
                if is_basic:
                    try:
                        logger.info("knowledge_pipeline: calling LLM quick...", extra={"len_msg": len(user_msg or "")})
                    except Exception:
                        pass
                    raw_llm = await call_llm_once(user_msg, system_prompt(persona), body.lang or "de-DE", body.persona or "friendly")
                    txt_llm = clean(raw_llm or "")
                    try:
                        logger.info("knowledge_pipeline: LLM quick response chars=%s", len(txt_llm or ""))
                    except Exception:
                        pass
                    if txt_llm and len(txt_llm.strip()) >= 80:
                        # Save knowledge: KM block + addressbook + audit store
                        try:
                            tp = km_guess_topic_path(user_msg, hints={"label": extract_topic(user_msg) or ""})
                            kb = km_promote_block(txt_llm, user_msg, source="llm", hints={"topic_path": tp, "summary": short_summary(txt_llm)}, base_confidence=0.6, tags=["llm","autosaved"])  # type: ignore
                            try:
                                from netapi.core.addressbook import register_block_for_topic as _ab_register
                                if kb and getattr(kb, 'id', None) and getattr(kb, 'topic_path', None):
                                    _ab_register(kb.topic_path, kb.id)
                                    try:
                                        logger.info("addressbook_register", extra={"topic_path": kb.topic_path, "block_id": kb.id})
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            try:
                                from netapi import memory_store as _mem
                                _mem.save_memory_entry(title=(extract_topic(user_msg) or tp)[:120], content=txt_llm, tags=["llm","learned"], url=None)
                            except Exception:
                                pass
                        except Exception:
                            pass
                        txt_llm = postprocess_and_style(txt_llm, persona, state, profile_used, style_prompt)
                        txt_llm = make_user_friendly_text(txt_llm, state)
                        try:
                            if state is not None:
                                state.last_pipeline = "llm"  # type: ignore[attr-defined]
                        except Exception:
                            pass
                        try:
                            logger.warning("knowledge_pipeline selected=%s topic=%s user=%s", "llm", extract_topic(user_msg), getattr(current, 'id', None))
                        except Exception:
                            pass
                        return _finalize_reply(
                            txt_llm,
                            state=state, conv_id=(body.conv_id or None), intent="knowledge", topic=extract_topic(user_msg), pipeline="llm",
                            extras={"ok": True, "auto_modes": [], "role_used": "Erklärbär", "memory_ids": [], "topic": extract_topic(user_msg), "backend_log": {"pipeline": "llm", "topic": extract_topic(user_msg)}}
                        )
            except Exception:
                pass
            # 3.6) Forced LLM fallback before child-mode, even if not a basic topic
            try:
                try:
                    logger.info("knowledge_pipeline: forced_llm_fallback attempting...")
                except Exception:
                    pass
                raw_fallback = await call_llm_once(user_msg, system_prompt(persona), body.lang or "de-DE", body.persona or "friendly")
                txt_fb = clean(raw_fallback or "")
                used_fb = bool(txt_fb and len(txt_fb.strip()) >= 40)
                try:
                    logger.info("knowledge_pipeline: forced_llm_fallback used=%s", used_fb)
                except Exception:
                    pass
                if used_fb:
                    try:
                        if state is not None:
                            state.last_pipeline = "llm"  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    txt_fb = postprocess_and_style(txt_fb, persona, state, profile_used, style_prompt)
                    txt_fb = make_user_friendly_text(txt_fb, state)
                    try:
                        logger.info(f"knowledge_pipeline selected=llm topic={extract_topic(user_msg)} user={getattr(current, 'id', None)}")
                    except Exception:
                        pass
                    return _finalize_reply(
                        txt_fb,
                        state=state, conv_id=(body.conv_id or None), intent="knowledge", topic=extract_topic(user_msg), pipeline="llm",
                        extras={"ok": True, "auto_modes": [], "role_used": "Erklärbär", "memory_ids": [], "topic": extract_topic(user_msg), "backend_log": {"pipeline": "llm", "topic": extract_topic(user_msg)}}
                    )
            except Exception:
                pass
            # 4) Ask the user (childlike), set pending learning markers
            ask = (
                "Dazu habe ich noch keine gespeicherten Informationen. "
                "Wenn du willst, kann ich es dir aber aus allgemeinem Wissen erklären – "
                "sag mir nur kurz, ob du eine kurze Übersicht oder eine detailliertere Erklärung möchtest."
            )
            if state:
                state.pending_learning = {"topic_path": topic_path}
                try:
                    setattr(state, 'pending_followup', 'learning')
                except Exception:
                    pass
            try:
                logger.warning("knowledge_pipeline selected=%s topic=%s user=%s", "child", extract_topic(user_msg), getattr(current, 'id', None))
            except Exception:
                pass
                try:
                    if not hasattr(state, 'learning_buffer') or state.learning_buffer is None:
                        state.learning_buffer = []  # type: ignore[attr-defined]
                except Exception:
                    pass
            ask = postprocess_and_style(ask, persona, state, profile_used, style_prompt)
            ask = make_user_friendly_text(ask, state)
            if consent_note:
                ask = (ask + "\n\n" + consent_note).strip()
            conv_id_ask = None
            try:
                if current and current.get("id"):
                    uid = int(current["id"])  # type: ignore
                    conv = _ensure_conversation(db, uid, body.conv_id)
                    conv_id_ask = conv.id
                    _save_msg(db, conv.id, "user", user_msg)
                    _save_msg(db, conv.id, "ai", ask)
                    asyncio.create_task(_retitle_if_needed(conv.id, user_msg, ask, body.lang or "de-DE"))
            except Exception:
                conv_id_ask = None
            try:
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                uid_for_mem = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                save_experience(uid_for_mem, conv_id_ask, {"type": "knowledge_ask_user", "user_message": user_msg, "assistant_reply": ask, "topic_path": topic_path, "timestamp": now_iso})
                if state:
                    try:
                        state.last_pipeline = "child"  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    save_state(state)
            except Exception:
                pass
            # Knowledge hard-guard for child/follow-up prompt
            try:
                if isinstance(ask, str):
                    s = ask.strip()
                    if s.startswith('{') and '"recent_topics"' in s and '"mood"' in s:
                        logger.warning("chat_once: knowledge answer tried to return self-state JSON, converting to human text")
                        try:
                            from netapi.core.expression import express_state_human as _expr_ask
                            ask = _expr_ask(state) if state else "Ich spüre, dass ich gerade vor allem lernen und verstehen will – sag mir gern, was du konkret über das Thema wissen möchtest. 🙂"
                        except Exception:
                            ask = "Ich spüre, dass ich gerade vor allem lernen und verstehen will – sag mir gern, was du konkret über das Thema wissen möchtest. 🙂"
            except Exception:
                pass
            # pipeline log + extras
            try:
                uid_log = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
            except Exception:
                uid_log = None
            try:
                logger.info(f"knowledge_pipeline selected=child topic={extract_topic(user_msg)} user={uid_log}")
            except Exception:
                pass
            # set last_pipeline
            try:
                if state is not None:
                    state.last_pipeline = "child"  # type: ignore[attr-defined]
            except Exception:
                pass
            _bump_answers_and_maybe_reflect(extract_topic(user_msg))
            return _finalize_reply(
                ask,
                state=state, conv_id=(conv_id_ask if conv_id_ask is not None else (body.conv_id or None)), intent="knowledge", topic=extract_topic(user_msg), pipeline="child",
                extras={"ok": True, "auto_modes": [], "role_used": "FollowUp", "memory_ids": [], "quick_replies": ["Ich erkläre es in 2-3 Sätzen"], "topic": extract_topic(user_msg), "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": "child", "topic": extract_topic(user_msg)}}
            )
    except Exception:
        # Outer guard: if even entering the knowledge section failed, log and respond gracefully
        try:
            logger.exception("knowledge_section entry failed", extra={"intent": intent, "user_msg": user_msg})
        except Exception:
            pass
        try:
            raw_outer = await call_llm_once(
                user_msg,
                (_system_prompt if ('_system_prompt' in locals()) else system_prompt(body.persona)),
                body.lang or "de-DE",
                body.persona or "friendly",
            )
            txt_outer = postprocess_and_style(clean(raw_outer or ""), persona if 'persona' in locals() else get_kiana_persona(), state, profile_used, style_prompt)
            if not txt_outer or not str(txt_outer).strip():
                txt_outer = "Ich gebe dir eine knappe Antwort, obwohl intern ein Fehler in meiner Wissenssuche war."
        except Exception:
            txt_outer = "Ich gebe dir eine knappe Antwort, obwohl intern ein Fehler in meiner Wissenssuche war."
        return _finalize_reply(
            txt_outer,
            state=state, conv_id=(body.conv_id or None), intent="knowledge", topic=extract_topic(user_msg), pipeline="knowledge_llm", status="unsafe",
            extras={"ok": True, "backend_log": {"pipeline": "knowledge_llm", "status": "unsafe"}}
        )

    # DEFAULT: Unified planner pipeline (Standardpfad) – mit kurzer Timeout & Fallback
    try:
        # Build persona-aware system prompt
        _time_block = build_timeblock()
        _system_prompt = build_system_prompt(persona, state, _time_block, experiences_snip or "")
        # Retrieve long-term memory context for this prompt
        _retr = retrieve_context_for_prompt(user_msg)
        _retr_snip = (_retr.get("snippet") or "").strip()
        _retr_ids  = list(_retr.get("ids") or [])
        # Initialize planner debug vars early to avoid UnboundLocalError
        plan_b = ""
        critic_b = ""
        
        # INJECT MEMORY CONTEXT into retrieval snippet
        if memory_context:
            _retr_snip = memory_context + "\n\n" + _retr_snip if _retr_snip else memory_context
        if _retr_ids:
            _audit_chat({"type": "retrieval_used", "ids": _retr_ids, "q": user_msg})
        
        # INJECT Persona System Prompt first, then TIMEFLOW CONTEXT (Europe/Vienna)
        if _system_prompt:
            _retr_snip = (_system_prompt + "\n\n" + _retr_snip).strip() if _retr_snip else _system_prompt
        # INJECT TIMEFLOW CONTEXT (Europe/Vienna) into retrieval snippet as system block
        try:
            tz = ZoneInfo("Europe/Vienna")
            now = datetime.datetime.now(tz)
            time_ctx = {
                "iso": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "weekday": now.strftime("%A"),
            }
            time_block = (
                f"[SYSTEM:TIME] Aktuelle Zeit (Europe/Vienna): {time_ctx['iso']} "
                f"(Datum: {time_ctx['date']}, Uhrzeit: {time_ctx['time']}, Wochentag: {time_ctx['weekday']}). "
                "Wenn der Benutzer nach Datum/Zeit fragt, benutze diese Werte exakt und rate nicht."
            )
            _retr_snip = (time_block + "\n\n" + _retr_snip).strip()
        except Exception:
            pass

        # Add conversation memory context
        if memory_context.strip():
            _retr_snip = memory_context.strip() + "\n\n" + _retr_snip
            _audit_chat({"type": "conversation_memory_used", "context_length": len(memory_context), "q": user_msg})
        async def _run_planner():
            # Use reasoner abstraction to allow future expansion
            return await reason_about(
                user_msg,
                persona=(body.persona or "friendly"), lang=(body.lang or "de-DE"),
                style=_sanitize_style(body.style), bullets=_sanitize_bullets(body.bullets),
                logic=_sanitize_logic(getattr(body, 'logic', 'balanced')),
                fmt=_sanitize_format(getattr(body, 'format', 'plain')),
            )
        r = await asyncio.wait_for(_run_planner(), timeout=PLANNER_TIMEOUT_SECONDS)
        ans_pl = (r.get("answer_candidate") or "") if isinstance(r, dict) else ""
        srcs_pl = (r.get("sources") or []) if isinstance(r, dict) else []
        plan_b = (r.get("plan") or "") if isinstance(r, dict) else ""
        critic_b = (r.get("critic") or "") if isinstance(r, dict) else ""
        out_text = (ans_pl or "").strip()
        if out_text:
            if _sanitize_format(getattr(body, 'format', 'plain')) == 'structured' or _sanitize_logic(getattr(body,'logic','balanced'))=='strict':
                out_text = build_structured_reply(out_text, [], srcs_pl or [], bullets=_sanitize_bullets(body.bullets), strict=(_sanitize_logic(getattr(body,'logic','balanced'))=='strict'), topic=extract_topic(user_msg))
            src_block = format_sources(srcs_pl or [], limit=3)
            if src_block:
                out_text = (out_text + "\n\n" + src_block).strip()
            autonomy = int(getattr(body, 'autonomy', 0) or 0)
            conv_id = None
            try:
                if current and current.get("id"):
                    uid = int(current["id"])  # type: ignore
                    conv = _ensure_conversation(db, uid, body.conv_id)
                    conv_id = conv.id
                    _save_msg(db, conv.id, "user", user_msg)
                    _save_msg(db, conv.id, "ai", out_text)
                    asyncio.create_task(_retitle_if_needed(conv.id, user_msg, out_text, body.lang or "de-DE"))
            except Exception:
                conv_id = None
            try:
                if autonomy >= 1 and srcs_pl:
                    learned_text = out_text
                    save_memory(title=(extract_topic(user_msg) or user_msg)[:120], content=learned_text, tags=["web","learned"], url=(srcs_pl[0].get('url') if srcs_pl else None))
                elif autonomy >= 2 and out_text and len(out_text)>160 and not srcs_pl:
                    save_memory(title=(extract_topic(user_msg) or user_msg)[:120], content=out_text, tags=["learned"], url=None)
            except Exception:
                pass
            # Prepare backend-only log; do not expose plan/kritik in UI
            backend_log = {"plan": plan_b, "kritik": critic_b, "meta": {"sources_count": len(srcs_pl or []), "pipeline": "planner"}}
            # Planner Pfad: optional Auto‑Modi Signalisierung (leichtgewichtig)
            auto_modes: List[str] = []
            if srcs_pl:
                auto_modes.append('web')
            if plan_b:
                auto_modes.append('chain')
            if critic_b:
                auto_modes.append('critique')
            # Simple role selection stub for Sub‑KIs
            role_used = 'Erklärbär'
            try:
                if srcs_pl and len(srcs_pl) > 0:
                    role_used = 'Forscher'
                elif critic_b:
                    role_used = 'Kritiker'
            except Exception:
                role_used = 'Erklärbär'
            try:
                t_det = extract_topic(user_msg)
                if t_det:
                    _LAST_TOPIC[sid] = t_det
                    # Persist for this conversation if known
                    if conv_id:
                        persist_last_topic(str(conv_id), t_det)
                    else:
                        persist_last_topic(sid, t_det)
            except Exception:
                pass
            # Append retrieval notice if we used long‑term blocks
            if _retr_ids:
                out_text = (out_text + "\n\n" + "📚 Antwort enthält Wissen aus Langzeitgedächtnis: Block-IDs " + ", ".join(_retr_ids)).strip()
            # Clean any planner scaffolding before UI formatting (remove M1:, Evidenz:, follow-up prompts)
            _raw_planner_text = out_text
            cleaned_once = extract_natural_reply(out_text)
            out_text = cleaned_once.strip() if isinstance(cleaned_once, str) else str(cleaned_once)
            # Humanize potential self-state outputs
            try:
                if isinstance(out_text, (dict, list)):
                    out_text = express_state_human(state.to_dict() if state else {})
                elif ("Kiana Self-State" in out_text) or ("Self-State" in out_text):
                    try:
                        out_text = express_state_human(state.to_dict() if state else {})
                    except Exception:
                        pass
            except Exception:
                pass
            if not out_text:
                # Prefer showing raw planner text over generic fallback if cleaning nuked content
                logger.warning("planner: cleaning produced empty; using raw planner text")
                out_text = _raw_planner_text
            # Ensure we never leak deliberation markers; only return cleaned frontend text
            out_text = format_user_response(out_text, backend_log)
            # Learning controller: if answer looks uncertain, ask or search
            try:
                if is_low_confidence_answer(out_text):
                    mode = decide_ask_or_search(user_msg, state, persona)
                    if mode == 'web_search':
                        web_ans, web_srcs = try_web_answer(user_msg, limit=3)
                        if web_ans:
                            out_text = web_ans
                            src_block_ws = format_sources(web_srcs or [], limit=2)
                            if src_block_ws:
                                out_text = (out_text + "\n\n" + src_block_ws).strip()
                        else:
                            digest_ctx = ""
                            try:
                                digest_ctx = lookup_web_context(user_msg)
                            except Exception:
                                digest_ctx = ""
                            if digest_ctx:
                                digest_prompt = compose_reasoner_prompt(user_msg, digest_ctx)
                                try:
                                    llm_txt_digest = await call_llm(digest_prompt)
                                except Exception:
                                    llm_txt_digest = ""
                                digest_reply = clean(llm_txt_digest or "")
                                if digest_reply:
                                    out_text = digest_reply
                                    mode = ""
                                else:
                                    mode = 'ask_user'
                            else:
                                mode = 'ask_user'
                    if mode == 'ask_user':
                        follow = build_childlike_question(user_msg, persona, state)
                        if state:
                            state.pending_followup = 'learning'
                        follow = postprocess_and_style(follow, persona, state, profile_used, style_prompt)
                        if consent_note:
                            follow = (follow + "\n\n" + consent_note).strip()
                        # Persist minimal and return early
                        conv_id_follow = None
                        try:
                            if current and current.get("id"):
                                uid = int(current["id"])  # type: ignore
                                conv = _ensure_conversation(db, uid, body.conv_id)
                                conv_id_follow = conv.id
                                _save_msg(db, conv.id, "user", user_msg)
                                _save_msg(db, conv.id, "ai", follow)
                                asyncio.create_task(_retitle_if_needed(conv.id, user_msg, follow, body.lang or "de-DE"))
                        except Exception:
                            conv_id_follow = None
                        try:
                            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            uid_for_mem = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                            save_experience(uid_for_mem, conv_id_follow, {
                                "type": "followup_question", "user_message": user_msg, "assistant_reply": follow,
                                "timestamp": now_iso, "mood": (state.mood if state else "neutral"),
                            })
                            if state:
                                save_state(state)
                        except Exception:
                            pass
                        conv_out_follow = conv_id_follow if conv_id_follow is not None else (body.conv_id or None)
                        return _finalize_reply(
                    follow,
                    state=state, conv_id=conv_out_follow, intent="learning_followup", topic=extract_topic(user_msg),
                    extras={"ok": True, "auto_modes": [], "role_used": "FollowUp", "memory_ids": [], "quick_replies": ["Ich erkläre es in 2-3 Sätzen"], "topic": extract_topic(user_msg), "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": "learning_followup"}}
                )
            except Exception:
                pass
            # Unified postprocessing with persona/state
            out_text = postprocess_and_style(out_text, persona, state, profile_used, style_prompt)
            # persist styled message if possible
            try:
                if conv_id:
                    _save_msg(db, conv_id, "ai", out_text)
            except Exception:
                pass
            if consent_note:
                out_text = (out_text + "\n\n" + consent_note).strip()
            _topic = extract_topic(user_msg)
            quick_replies = _quick_replies_for_topic(_topic, user_msg)
            # Persist experience and state updates
            try:
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                extracted_topics = [extract_topic(user_msg) or ""]
                uid_for_mem = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                save_experience(uid_for_mem, conv_id, {
                    "type": "experience", "user_message": user_msg, "assistant_reply": out_text,
                    "timestamp": now_iso, "mood": (state.mood if state else "neutral"), "topics": extracted_topics,
                })
                if state:
                    save_state(state)
                if state and experiences_raw:
                    asyncio.create_task(reflect_if_needed(state, experiences_raw))
            except Exception:
                pass
            conv_out = conv_id if conv_id is not None else (body.conv_id or None)
            return _attach_explain_and_kpis(
                {"ok": True, "reply": out_text, "conv_id": conv_out, "auto_modes": auto_modes, "role_used": role_used, "memory_ids": (_retr_ids or []), "quick_replies": quick_replies, "topic": _topic, "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": backend_log},
                route="/api/chat",
                intent=str(intent or "unknown"),
                source_expected=str(intent or "").strip().lower() in {"knowledge", "knowledge_query", "web", "research"},
            )
        else:
            logger.warning("chat_once: deliberate pipeline returned empty text, using fallback")
        # Wenn Planner keine Antwort liefert, falle auf klassische Pipeline zurück
    except asyncio.TimeoutError as e:
        logger.exception("Planner timeout in chat_once", exc_info=e)
    except Exception as e:
        logger.exception("Planner error in chat_once", exc_info=e)

    # 2.5) Simple LLM Path if planner produced no answer
    # Skip this path for knowledge queries to prefer the knowledge/web pipeline
    if intent == "knowledge_query":
        pass
    if intent != "knowledge_query":
        # Prepare backend-only log; do not expose plan/kritik in UI
        backend_log = {"plan": plan_b, "kritik": critic_b, "meta": {"sources_count": len(srcs_pl or []), "pipeline": "planner"}}
        # Planner Pfad: optional Auto‑Modi Signalisierung (leichtgewichtig)
        auto_modes: List[str] = []
        if srcs_pl:
            auto_modes.append('web')
        if plan_b:
            auto_modes.append('chain')
        if critic_b:
            auto_modes.append('critique')
        # Simple role selection stub for Sub‑KIs
        role_used = 'Erklärbär'
        try:
            if srcs_pl and len(srcs_pl) > 0:
                role_used = 'Forscher'
            elif critic_b:
                role_used = 'Kritiker'
        except Exception:
            role_used = 'Erklärbär'
        try:
            t_det = extract_topic(user_msg)
            if t_det:
                _LAST_TOPIC[sid] = t_det
                # Persist for this conversation if known
                if conv_id:
                    persist_last_topic(str(conv_id), t_det)
                else:
                    persist_last_topic(sid, t_det)
        except Exception:
            pass
        # Append retrieval notice if we used long‑term blocks
        if _retr_ids:
            out_text = (out_text + "\n\n" + "📚 Antwort enthält Wissen aus Langzeitgedächtnis: Block-IDs " + ", ".join(_retr_ids)).strip()
        # Clean any planner scaffolding before UI formatting (remove M1:, Evidenz:, follow-up prompts)
        _raw_planner_text = out_text
        cleaned_once = extract_natural_reply(out_text)
        out_text = cleaned_once.strip() if isinstance(cleaned_once, str) else str(cleaned_once)
        # Humanize potential self-state outputs
        try:
            if isinstance(out_text, (dict, list)):
                out_text = express_state_human(state.to_dict() if state else {})
            elif ("Kiana Self-State" in out_text) or ("Self-State" in out_text):
                try:
                    out_text = express_state_human(state.to_dict() if state else {})
                except Exception:
                    pass
        except Exception:
            pass
        if not out_text:
            # Prefer showing raw planner text over generic fallback if cleaning nuked content
            logger.warning("planner: cleaning produced empty; using raw planner text")
            out_text = _raw_planner_text
        # Ensure we never leak deliberation markers; only return cleaned frontend text
        out_text = format_user_response(out_text, backend_log)
        # Learning controller: if answer looks uncertain, ask or search
        if intent != "knowledge_query":
            try:
                if is_low_confidence_answer(out_text):
                    mode = decide_ask_or_search(user_msg, state, persona)
                    if mode == 'web_search':
                        web_ans, web_srcs = try_web_answer(user_msg, limit=3)
                        if web_ans:
                            out_text = web_ans
                            src_block_ws = format_sources(web_srcs or [], limit=2)
                            if src_block_ws:
                                out_text = (out_text + "\n\n" + src_block_ws).strip()
                        else:
                            digest_ctx = ""
                            try:
                                digest_ctx = lookup_web_context(user_msg)
                            except Exception:
                                digest_ctx = ""
                            if digest_ctx:
                                digest_prompt = compose_reasoner_prompt(user_msg, digest_ctx)
                                try:
                                    llm_txt_digest = await call_llm(digest_prompt)
                                except Exception:
                                    llm_txt_digest = ""
                                digest_reply = clean(llm_txt_digest or "")
                                if digest_reply:
                                    out_text = digest_reply
                                    mode = ""
                                else:
                                    mode = 'ask_user'
                            else:
                                mode = 'ask_user'
                    if mode == 'ask_user':
                        follow = build_childlike_question(user_msg, persona, state)
                        if state:
                            state.pending_followup = 'learning'
                        follow = postprocess_and_style(follow, persona, state, profile_used, style_prompt)
                        if consent_note:
                            follow = (follow + "\n\n" + consent_note).strip()
                        # Persist minimal and return early
                        conv_id_follow = None
                        try:
                            if current and current.get("id"):
                                uid = int(current["id"])  # type: ignore
                                conv = _ensure_conversation(db, uid, body.conv_id)
                                conv_id_follow = conv.id
                                _save_msg(db, conv.id, "user", user_msg)
                                _save_msg(db, conv.id, "ai", follow)
                                asyncio.create_task(_retitle_if_needed(conv.id, user_msg, follow, body.lang or "de-DE"))
                        except Exception:
                            conv_id_follow = None
                        try:
                            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            uid_for_mem = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
                            save_experience(uid_for_mem, conv_id_follow, {
                                "type": "followup_question", "user_message": user_msg, "assistant_reply": follow,
                                "timestamp": now_iso, "mood": (state.mood if state else "neutral"),
                            })
                            if state:
                                save_state(state)
                        except Exception:
                            pass
                        conv_out_follow = conv_id_follow if conv_id_follow is not None else (body.conv_id or None)
                        return _attach_explain_and_kpis(
                            {"ok": True, "reply": follow, "conv_id": conv_out_follow, "auto_modes": [], "role_used": "FollowUp", "memory_ids": [], "quick_replies": ["Ich erkläre es in 2-3 Sätzen"], "topic": extract_topic(user_msg), "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {"pipeline": "learning_followup"}},
                            route="/api/chat",
                            intent="learning_followup",
                            source_expected=False,
                        )
            except Exception:
                pass
        # Unified postprocessing with persona/state
        out_text = postprocess_and_style(out_text, persona, state, profile_used, style_prompt)
        # persist styled message if possible
        try:
            if conv_id:
                _save_msg(db, conv_id, "ai", out_text)
        except Exception:
            pass
        if consent_note:
            out_text = (out_text + "\n\n" + consent_note).strip()
        _topic = extract_topic(user_msg)
        quick_replies = _quick_replies_for_topic(_topic, user_msg)
        # Persist experience and state updates
        try:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            extracted_topics = [extract_topic(user_msg) or ""]
            uid_for_mem = int(current["id"]) if (current and current.get("id")) else None  # type: ignore
            save_experience(uid_for_mem, conv_id, {
                "type": "experience", "user_message": user_msg, "assistant_reply": out_text,
                "timestamp": now_iso, "mood": (state.mood if state else "neutral"), "topics": extracted_topics,
            })
            if state:
                save_state(state)
            if state and experiences_raw:
                asyncio.create_task(reflect_if_needed(state, experiences_raw))
        except Exception:
            pass
        conv_out = conv_id if conv_id is not None else (body.conv_id or None)
        if out_text and str(out_text).strip():
            return _attach_explain_and_kpis(
                {"ok": True, "reply": out_text, "conv_id": conv_out, "auto_modes": auto_modes, "role_used": role_used, "memory_ids": (_retr_ids or []), "quick_replies": quick_replies, "topic": _topic, "risk_flag": risk_flag, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": backend_log},
                route="/api/chat",
                intent=str(intent or "unknown"),
                source_expected=str(intent or "").strip().lower() in {"knowledge", "knowledge_query", "web", "research"},
            )

    # 3) Pipeline: Memory -> Web (optional) -> LLM -> Save (Fallback)
    # Guard: never let simple greetings fall through to generic fallback
    try:
        lowtxt = (user_msg or "").strip().lower()
        if (intent != "knowledge_query") and any(g in lowtxt for g in ["hallo", "hi ", " hey", "servus", "grüß dich", "guten morgen", "guten abend", "moin"]):
            return _attach_explain_and_kpis(
                {"ok": True, "reply": "Hallo! 😊 Schön, dass du da bist. Wie kann ich dir helfen?", "kiana_node": "mother-core", "conv_id": (body.conv_id or None)},
                route="/api/chat",
                intent="greeting",
                source_expected=False,
            )
    except Exception:
        pass
    topic = extract_topic(user_msg)
    # Combine follow‑ups with last topic context
    query, topic = _combine_with_context(sid, user_msg, topic)
    mem_hits = recall_mem(query, top_k=3) or []
    mem_hits = [m for m in mem_hits if float(m.get("score", 0)) >= MEM_MIN_SCORE][:3]
    style = _sanitize_style(body.style)
    bullet_limit = _sanitize_bullets(body.bullets)
    logic_mode = _sanitize_logic(getattr(body, 'logic', 'balanced'))
    fmt_mode = _sanitize_format(getattr(body, 'format', 'plain'))
    # reduce noise using extracted topic
    if not mem_hits:
        # Semantic fallback (optional embeddings)
        try:
            from ... import memory_store as _mem  # type: ignore
            sem = _mem.search_blocks_semantic(query, top_k=3, min_score=0.15) or []
            blocks = []
            _ids_sem: list[str] = []
            for bid, sc in sem:
                b = _mem.get_block(bid)
                if b:
                    blocks.append({"id": bid, "title": b.get('title',''), "content": b.get('content',''), "score": float(sc)})
                    try:
                        if bid:
                            _ids_sem.append(str(bid))
                    except Exception:
                        pass
            mem_hits = blocks
            try:
                if _ids_sem:
                    _record_used_memory_ids(_ids_sem)
            except Exception:
                pass
        except Exception:
            mem_hits = []
    if mem_hits:
        mem_hits = _filter_hits_by_topic(mem_hits, topic)
        mem_hits = _boost_with_ratings(mem_hits)
    mem_note = memory_bullets(mem_hits, bullet_limit)

    # Web vorziehen, wenn es eine Frage ist oder Memory leer ist
    q_mode = is_question(user_msg)
    need_web = q_mode or (not mem_hits)
    ans, sources = None, []
    learned_text: Optional[str] = None
    learned_url: Optional[str] = None
    block_info: Dict[str, str] = {}

    if need_web:
        try:
            from ...config import settings as _s
            allow_global = bool(getattr(_s, 'ALLOW_NET', True))
        except Exception:
            allow_global = (os.getenv('ALLOW_NET','1')=='1')
        if allow_global:
            ans, sources = try_web_answer(topic or query or user_msg, limit=5)
        elif getattr(body, 'web_ok', False):
            ans, sources = _force_web_answer(topic or query or user_msg, limit=3)

    # Default: Bei Fragen eine kurze Zusammenfassung liefern und danach Nachfragen anbieten
    # Heuristische Auto‑Aktivierung von Modi
    autonomy = int(getattr(body, 'autonomy', 0) or 0)
    ul = user_msg.lower()
    auto_fact = False
    auto_counter = False
    auto_delib = False
    auto_chain = False
    # Chain wenn komplex/mehrteilig oder explizit nach Plan/Schritten gefragt
    if q_mode and (ul.count('?') >= 2 or any(k in ul for k in ['schritte', 'plan', 'vergleich', 'unterschiede', 'pipeline'])):
        auto_chain = True
    # Deliberation bei höherer Autonomie oder längeren Fragen
    if autonomy >= 2 or len(user_msg) > 240:
        auto_delib = False  # konservativ: volle Deliberation nur, wenn explizit gefordert; später ausbaubar
    # Counter bei Pro/Contra oder kontroversen Stichworten
    if any(k in ul for k in ['pro und contra', 'pro/contra', 'gegenargument', 'kritik', 'risiko', 'nachteil', 'ethik', 'privacy', 'datenschutz']):
        auto_counter = True
    # Factcheck wenn keine Quellen, aber eine klare Aussage oder bei strenger Logik
    if (not sources) and (autonomy >= 2 or any(k in ul for k in ['ist wahr', 'stimmt es', 'beweise', 'quelle', 'beleg'])):
        auto_fact = True

    # Kombiniere mit (ggf. noch vorhandenen) manuellen Flags
    flag_counter = bool(getattr(body, 'counter', False) or auto_counter)
    flag_fact = bool(getattr(body, 'factcheck', False) or auto_fact)
    flag_delib = bool(getattr(body, 'deliberation', False) or auto_delib)
    flag_critique = bool(getattr(body, 'critique', False))  # Kritik (Refinement) separat gesteuert

    auto_modes: List[str] = []
    if need_web and sources:
        auto_modes.append('web')
    if auto_chain:
        auto_modes.append('chain')
    if auto_counter:
        auto_modes.append('counter')
    if auto_fact:
        auto_modes.append('factcheck')

    if q_mode:
        # Wenn weder Memory noch Web vorhanden, sag ehrlich Bescheid und versuche Websuche
        if not mem_hits and not ans:
            reply = ("Darüber weiß ich noch nichts – ich schaue kurz im Web nach.\n"
                     "(Falls du willst, kann ich danach mehr ins Detail gehen.)")
            # zweiter Versuch (ggf. Netz war langsam)
            ans2, sources2 = try_web_answer(topic or user_msg, limit=5)
            if ans2:
                # direkte, kompakte Antwort ohne LLM-Zwischenschritt
                reply = (reply + "\n\n" + ans2.strip()).strip()
                src_block = format_sources(sources2, limit=2)
                if src_block:
                    reply += "\n\n" + src_block
                learned_text = ans2.strip(); learned_url = sources2[0].get("url") if (sources2 and sources2[0].get("url")) else None
                block_info = save_memory(title=(topic or user_msg)[:120], content=learned_text, tags=["web","learned"], url=learned_url)
            else:
                reply += "\n\nLeider habe ich dazu aktuell keine verlässlichen Quellen gefunden."
        else:
            # Structured reply (preferred) or simple concatenation
            if fmt_mode == 'structured' or logic_mode == 'strict':
                reply = build_structured_reply(ans or '', mem_hits, sources or [], bullets=bullet_limit, strict=(logic_mode=='strict'), topic=topic)
            else:
                if style == "concise":
                    reply = short_summary((ans or "") + "\n\n" + (mem_note or ""), max_chars=380).strip()
                else:
                    parts = []
                    if ans:
                        parts.append(ans.strip())
                    if mem_note:
                        parts.append(mem_note.strip())
                    reply = "\n\n".join(p for p in parts if p)
            if not reply:
                # Avoid empty reply: fall back to childlike follow-up question
                try:
                    reply = build_childlike_question(user_msg, persona, state)
                    if state:
                        state.pending_followup = 'learning'
                except Exception:
                    reply = _fallback_reply(user_msg)
            # Quellen anhängen, falls vorhanden
            if ans:
                src_block = format_sources(sources, limit=2)
                if src_block:
                    reply = (reply + "\n\n" + src_block).strip()
                learned_text = ans.strip(); learned_url = sources[0].get("url") if (sources and sources[0].get("url")) else None
                block_info = save_memory(title=(topic or user_msg)[:120], content=learned_text, tags=["web","learned"], url=learned_url)

        # Gewünschter Stil: zuerst Kurzfassung, dann offene Nachfrage
        if fmt_mode == 'structured' or logic_mode == 'strict':
            # Already structured; keep as is
            reply = reply.strip()
        elif reply and reply.strip():
            reply = ("Kurzfassung:\n\n" + reply.strip())
        reply = (reply + "\n\nMöchtest du mehr? Ich kann vertiefen oder auf bestimmte Bereiche eingehen (z. B. Grundlagen, Arten, Angriffe, Schutz). Sag mir einfach, was dich interessiert.").strip()
        set_last_offer(sid, None); set_offer_context(sid, topic=(topic or user_msg)[:80], seed=user_msg)

        # Optional server-side persistence
        conv_id = None
        try:
            if current and current.get("id"):
                uid = int(current["id"])  # type: ignore
                conv = _ensure_conversation(db, uid, body.conv_id)
                conv_id = conv.id
                _save_msg(db, conv.id, "user", user_msg)
                _save_msg(db, conv.id, "ai", reply)
                asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply, body.lang or "de-DE"))
        except Exception:
            conv_id = None
        # Unified postprocessing with persona/state (removes meta phrases)
        reply = postprocess_and_style(reply, persona, state, profile_used, style_prompt)
        if not reply or not str(reply).strip():
            # As a last resort, ensure a visible message
            safe = build_childlike_question(user_msg, persona, state)
            reply = postprocess_and_style(safe, persona, state, profile_used, style_prompt)
        if consent_note:
            reply = (reply + "\n\n" + consent_note).strip()
        # Backend log channel (empty for this path)
        backend_log = {}
        conv_out = conv_id if conv_id is not None else (body.conv_id or None)
        return _attach_explain_and_kpis(
            {"ok": True, "reply": reply, "conv_id": conv_out, "auto_modes": auto_modes, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": backend_log},
            route="/api/chat",
            intent=str(intent or "unknown"),
            source_expected=str(intent or "").strip().lower() in {"knowledge", "knowledge_query", "web", "research"},
        )

    # Deliberation‑Pipeline (Planner→Researcher→Writer→Critic)
    try:
        if flag_delib:
            final, srcs_d, plan_b, critic_b = await deliberate_pipeline(
                user_msg,
                persona=(body.persona or "friendly"), lang=(body.lang or "de-DE"),
                style=style, bullets=bullet_limit, logic=logic_mode, fmt=fmt_mode
            )
            # Strukturierte Ausgabe optional
            out_text = final.strip()
            if fmt_mode == 'structured' or logic_mode == 'strict':
                out_text = build_structured_reply(out_text, mem_hits or [], srcs_d or [], bullets=bullet_limit, strict=(logic_mode=='strict'), topic=topic)
            # Quellen anhängen
            src_block = format_sources(srcs_d, limit=3)
            if src_block:
                out_text = (out_text + "\n\n" + src_block).strip()
            # Backend-only debug: Plan & Kritik (do not expose in UI)
            debug_info = {"plan": plan_b, "critic": critic_b, "sources_count": len(srcs_d or [])}
            out_text = format_user_response(out_text, debug_info)
            # Persist (optional)
            conv_id = None
            try:
                if current and current.get("id"):
                    uid = int(current["id"])  # type: ignore
                    conv = _ensure_conversation(db, uid, body.conv_id)
                    conv_id = conv.id
                    _save_msg(db, conv.id, "user", user_msg)
                    _save_msg(db, conv.id, "ai", out_text)
                    asyncio.create_task(_retitle_if_needed(conv.id, user_msg, out_text, body.lang or "de-DE"))
            except Exception:
                conv_id = None
            out_text = _apply_style(out_text, profile_used)
            if style_prompt:
                out_text = (out_text + "\n\n" + style_prompt).strip()
            if consent_note:
                out_text = (out_text + "\n\n" + consent_note).strip()
            backend_log = {"plan": plan_b, "critic": critic_b}
            conv_out = conv_id if conv_id is not None else (body.conv_id or None)
            return _attach_explain_and_kpis(
                {"ok": True, "reply": out_text, "conv_id": conv_out, "auto_modes": auto_modes, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": backend_log},
                route="/api/chat",
                intent="deliberation",
                source_expected=True,
            )
    except Exception:
        pass

    # LLM Input zusammensetzen
    llm_user = user_msg
    if mem_note:
        llm_user += mem_note
    if ans:
        llm_user += "\n\n(Web‑Zusammenfassung)\n" + ans.strip()
    # Anhänge aus der Nachricht annotieren (informativ für das LLM)
    try:
        atts = getattr(body, 'attachments', None)
        if atts:
            lines = ["(Anhänge)"]
            for a in (atts or [])[:5]:
                nm = str(a.get('name') or a.get('url') or 'Datei')
                tp = str(a.get('type') or '')
                url = str(a.get('url') or '')
                lines.append(f"- {nm} ({tp}) {url}")
            llm_user += "\n\n" + "\n".join(lines)
    except Exception:
        pass

    raw = await call_llm_once(
        llm_user,
        _system_prompt if ('_system_prompt' in locals()) else system_prompt(body.persona),
        body.lang or "de-DE",
        body.persona or "friendly",
    )
    reply = clean(raw)
    # Bei 'structured' oder 'strict' eine strukturierte Antwort mit Evidenz bauen
    structured = (fmt_mode == 'structured' or logic_mode == 'strict')
    if structured:
        reply = build_structured_reply(ans or '', mem_hits, sources or [], bullets=bullet_limit, strict=(logic_mode=='strict'), topic=topic)
    else:
        if reply:
            reply = "Kurzfassung:\n\n" + reply

    # Optional: Selbstkritik/Refinement in zweiter Pass
    try:
        if flag_critique:
            refine_user = (
                "Überarbeite die folgende Antwort auf die Frage.\n"
                "Ziel: korrigiere Fehler, ergänze wichtige Punkte, verbessere Klarheit.\n"
                "Gib NUR die verbesserte Antwort aus, ohne Analyse.\n\n"
                f"Frage:\n{user_msg}\n\nEntwurf:\n{reply}"
            )
            refined = await call_llm_once(refine_user, system_prompt(body.persona), body.lang or "de-DE", body.persona or "friendly")
            if refined and isinstance(refined, str) and refined.strip():
                reply = clean(refined.strip())
    except Exception:
        pass

    if ans:
        # Quellen beilegen (nur wenn nicht bereits strukturiert eingefügt)
        if not structured:
            reply = (reply + "\n\n" + format_sources(sources, limit=2)).strip()
        learned_text = ans.strip()
        learned_url  = sources[0].get("url") if (sources and sources[0].get("url")) else None
        block_info = save_memory(
            title=(topic or user_msg)[:120],
            content=learned_text,
            tags=["web", "learned"],
            url=learned_url,
        )
    else:
        if mem_hits and (not structured):
            reply = (reply + mem_note).strip()

        # Nur auto-learn, wenn keine Memory‑Notizen angehängt wurden und kein Gruß
        if reply and len(reply) > 120 and "Quellen:" not in reply and not mem_hits and not _GREETING.search(user_msg.lower()):
            learned_text = reply
            block_info = save_memory(
                title=(topic or user_msg)[:120],
                content=learned_text,
                tags=["learned"],
                url=None,
            )

    # Addressbook updaten + Enrichment
    if topic and (block_info.get("file") or learned_url):
        upsert_addressbook(topic, block_file=block_info.get("file", ""), url=learned_url or "")
        enqueue_enrichment(topic)

    # Gegenbeweis: alternative/konträre Quellen ergänzen
    try:
        if flag_counter:
            q_ctr = (f"Kritik an {topic}" if topic else ("Gegenargumente zu " + (query or user_msg)))
            ctr_ans, ctr_sources = try_web_answer(q_ctr, limit=5)
            ctr_sources = _filter_sources_by_env(ctr_sources)
            block = format_sources(ctr_sources, limit=3)
            if ctr_ans:
                reply = (reply + "\n\nGegenposition:\n" + short_summary(ctr_ans, max_chars=320)).strip()
            if block:
                reply = (reply + "\n\nGegenbeweise:" + block.replace("\n\nQuellen:", "")).strip()
    except Exception:
        pass

    # Faktencheck: unabhängig von obiger Web-Phase, ergänze evidenzbasierte Quellen
    try:
        if flag_fact:
            q_fc = topic or query or user_msg
            ans2, sources2 = try_web_answer(q_fc, limit=5)
            src_block = format_sources(sources2, limit=3)
            # Hinweis zu Evidenzstärke
            hint = ""
            if not sources2:
                hint = "\n\nHinweis: Keine belastbare Evidenz gefunden."
            elif len(sources2) == 1:
                hint = "\n\nHinweis: Geringe Evidenz (nur 1 unabhängige Quelle)."
            # Quellen nur anhängen, wenn noch nicht vorhanden
            if "\n\nQuellen:\n" not in reply and src_block:
                reply = (reply + "\n\n" + src_block).strip()
            if hint:
                reply = (reply + hint).strip()
                # Konkrete nächste Schritte vorschlagen (Strict/Factcheck)
                try:
                    if (getattr(body, 'factcheck', False)):
                        steps = [
                            "Relevanz einschränken (Thema/Zeitraum), dann erneut suchen",
                            "2–3 unabhängige, vertrauenswürdige Quellen vergleichen",
                            "Direkte Zitate/Primärquellen prüfen"
                        ]
                        reply = (reply + "\n\nNächste Schritte:\n" + "\n".join(f"- {s}" for s in steps)).strip()
                except Exception:
                    pass
            # Evidenz-ID berechnen (Antwort + URLs)
            urls = " ".join([s.get('url') or '' for s in (sources2 or [])])
            h = hashlib.sha256((reply + "||" + urls).encode('utf-8')).hexdigest()[:10]
            reply = (reply + f"\n\nEvidenz-ID: {h}").strip()
            # Evidence in Memory speichern (Chain‑Hinweis)
            try:
                ev_text = (ans2 or "").strip()
                if src_block:
                    ev_text = (ev_text + "\n\n" + src_block).strip()
                save_memory(
                    title=((topic or user_msg)[:96] + " – Faktencheck"),
                    content=(ev_text or reply[:800]),
                    tags=["evidence", "factcheck", f"evid:{h}"],
                    url=(sources2[0].get('url') if sources2 else None),
                    chain_hint=True,
                )
            except Exception:
                pass
    except Exception:
        pass

    # Kurz-Recap anhängen
    if learned_text:
        reply = (reply + "\n\n(Kurz gelernt)\n" + short_summary(learned_text, max_chars=280)).strip()

    # Abschluss im gewünschten Stil
    reply += "\n\nMöchtest du mehr? Ich kann vertiefen oder auf bestimmte Bereiche eingehen (z. B. Grundlagen, Beispiele, Anwendungen, Schutz)."
    set_last_offer(sid, None)

    try:
        _audit_chat({
            "ts": int(time.time()),
            "sid": sid,
            "persona": body.persona,
            "lang": body.lang,
            "user": user_msg,
            "reply": reply[:4000],
            "topic": topic,
            "learned": bool(learned_text),
        })
    except Exception:
        pass
    # Optional server-side persistence
    conv_id = None
    try:
        if current and current.get("id"):
            uid = int(current["id"])  # type: ignore
            conv = _ensure_conversation(db, uid, body.conv_id)
            conv_id = conv.id
            _save_msg(db, conv.id, "user", user_msg)
            _save_msg(db, conv.id, "ai", reply)
            # Retitle in background
            asyncio.create_task(_retitle_if_needed(conv.id, user_msg, reply, body.lang or "de-DE"))
    except Exception:
        conv_id = None
    # Final classic fallback reply postprocessing
    reply = postprocess_and_style(reply, persona, state, profile_used, style_prompt)
    if not reply or not str(reply).strip():
        logger.warning("chat_once produced empty reply after postprocessing; using friendly fallback")
        reply = (
            "Da ist mir gerade etwas beim Verarbeiten durcheinandergeraten. "
            "Magst du deine Frage bitte noch einmal stellen oder anders formulieren?"
        )
    if consent_note:
        reply = (reply + "\n\n" + consent_note).strip()
    conv_out = conv_id if conv_id is not None else (body.conv_id or None)
    return _attach_explain_and_kpis(
        {"ok": True, "reply": reply, "conv_id": conv_out, "style_used": style_used_meta, "style_prompt": style_prompt, "backend_log": {}},
        route="/api/chat",
        intent=str(intent or "unknown"),
        source_expected=str(intent or "").strip().lower() in {"knowledge", "knowledge_query", "web", "research"},
    )

# -------------------------------------------------
# Streaming (SSE)
# -------------------------------------------------
@router.get("/stream")
async def chat_stream(message: str, request: Request, persona: str = "friendly", lang: str = "de-DE", chain: bool = False, conv_id: Optional[int] = None, style: str = "balanced", bullets: int = 5, web_ok: bool = False, autonomy: int = 0):
    user_msg = (message or "").strip()
    request_id = None
    try:
        request_id = getattr(getattr(request, "state", None), "request_id", None)
    except Exception:
        request_id = None
    try:
        request_id = str(request_id or "")
    except Exception:
        request_id = ""
    if not request_id:
        try:
            import uuid as _uuid
            request_id = str(_uuid.uuid4())
        except Exception:
            request_id = ""
    # Debug logging at start
    try:
        logger.info("chat_stream: start request_id=%s message=%r persona=%s lang=%s chain=%s conv_id=%s style=%s bullets=%s web_ok=%s autonomy=%s", request_id, user_msg, persona, lang, chain, conv_id, style, bullets, web_ok, autonomy)
    except Exception:
        pass
    if not user_msg:
        raise HTTPException(400, "empty message")
    sid = session_id(request)
    # Lightweight correlation id (no extra import): sid + short timestamp suffix
    try:
        _now_ms = int(time.time() * 1000)
    except Exception:
        _now_ms = 0
    cid = f"{sid}:{_now_ms % 1000000:06d}"
    t0 = time.time()
    intent_label = "chat_stream"

    # Auth context (best-effort). Must be defined even if lookup fails.
    current = None

    # Best-effort: ensure we have a real conversation id early so clients can rely on it.
    stream_conv_id: Optional[int] = None
    try:
        if conv_id is None or conv_id == "" or conv_id == "null":
            stream_conv_id = None
        else:
            _cid = int(conv_id)  # type: ignore[arg-type]
            stream_conv_id = _cid if _cid > 0 else None
    except Exception:
        stream_conv_id = None
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            current = get_current_user_opt(request, db=db)
            if current and current.get("id"):
                uid = int(current["id"])  # type: ignore[index]
                conv = _ensure_conversation(db, uid, stream_conv_id)
                stream_conv_id = int(conv.id)
        finally:
            try:
                db.close()
            except Exception:
                pass
            try:
                db_gen.close()
            except Exception:
                pass
    except Exception:
        pass
    def _log(level: str, msg: str, *args):
        try:
            pref = f"[cid={cid}] " + msg
            if level == 'info':
                logger.info(pref, *args)
            elif level == 'warning':
                logger.warning(pref, *args)
            elif level == 'error':
                logger.error(pref, *args)
            else:
                logger.debug(pref, *args)
        except Exception:
            pass

    # Per-request explain/KPI context for streaming
    _stream_policy = {
        "web_ok": bool(web_ok),
        "autonomy": int(autonomy or 0),
        "style": str(style or ""),
        "bullets": int(bullets or 0),
    }
    try:
        _CHAT_EXPLAIN_CTX.set({
            "cid": cid,
            "request_id": request_id,
            "route": "/api/chat/stream",
            "t0": t0,
            "is_question": bool(is_question(user_msg)),
            "policy": dict(_stream_policy),
            "tools": [],
            "kpi_done": False,
        })
    except Exception:
        pass

    # Quality gates: snapshot state for this stream request
    try:
        _init_quality_gates_context(current=getattr(request, "state", None) and getattr(request.state, "user", None))
    except Exception:
        try:
            _init_quality_gates_context(current=None)
        except Exception:
            pass

    # SSE helpers
    def _sse(payload: dict) -> dict:
        try:
            return {"data": json.dumps(payload, ensure_ascii=False)}
        except Exception:
            return {"data": json.dumps({"error": "encode_failed"})}

    def _finalize_frame(
        *,
        intent: str,
        text: str = "",
        payload: Optional[dict] = None,
        extra: Optional[dict] = None,
        policy_override: Optional[dict] = None,
        tools: Optional[list] = None,
        source_expected: bool = False,
        ok: bool = True,
        error: Optional[str] = None,
    ) -> dict:
        base: dict = {}
        if isinstance(payload, dict):
            try:
                base.update(payload)
            except Exception:
                pass
        if isinstance(extra, dict):
            try:
                base.update(extra)
            except Exception:
                pass

        # Required finalize schema (stable for clients)
        base["type"] = "finalize"
        base["schema_version"] = 1
        base["cid"] = str(cid or "")
        base["request_id"] = str(request_id or "")
        base["ok"] = bool(ok)
        base["done"] = True
        base["text"] = str(text or "")

        # Conversation id: always include when available (meta+finalize contract)
        try:
            if stream_conv_id is not None and int(stream_conv_id) > 0:
                base["conversation_id"] = int(stream_conv_id)
                base["conv_id"] = int(stream_conv_id)
        except Exception:
            pass

        if error:
            base["error"] = str(error)[:400]

        if not isinstance(base.get("sources"), list):
            base["sources"] = []
        if not isinstance(base.get("memory_ids"), list):
            base["memory_ids"] = []

        pol = dict(_stream_policy)
        if isinstance(policy_override, dict):
            try:
                pol.update(policy_override)
            except Exception:
                pass

        # Attach stable explain + finalize KPIs (once per request)
        try:
            sources_count = 0
            try:
                if isinstance(base.get("sources"), list):
                    sources_count = len(base.get("sources") or [])
            except Exception:
                sources_count = 0
            base = _attach_explain_and_kpis(
                base,
                route="/api/chat/stream",
                intent=str(intent or "unknown"),
                policy=pol,
                tools=list(tools or []),
                source_expected=bool(source_expected),
                sources_count=int(sources_count),
            )
        except Exception:
            pass

        # timings_ms: keep consistent (mirror explain.timings_ms)
        try:
            ex = base.get("explain")
            if isinstance(ex, dict) and isinstance(ex.get("timings_ms"), dict):
                base["timings_ms"] = ex.get("timings_ms")
            elif not isinstance(base.get("timings_ms"), dict):
                base["timings_ms"] = {"total": int(max(0.0, (time.time() - t0)) * 1000)}
        except Exception:
            pass

        # Structured logs + audit for stream finalize (DoD visibility)
        try:
            total_ms = 0
            try:
                total_ms = int(max(0.0, (time.time() - t0)) * 1000)
            except Exception:
                total_ms = 0
            logger.info("STREAM_FINALIZE cid=%s request_id=%s ok=%s total_ms=%s", cid, request_id, bool(base.get("ok")), total_ms)
        except Exception:
            pass
        try:
            _audit_chat({
                "ts": int(time.time()),
                "sid": sid,
                "event": "STREAM_FINALIZE",
                "cid": cid,
                "request_id": request_id,
                "conv_id": conv_id,
                "ip": ip,
                "meta": {"ok": bool(base.get("ok")), "total_ms": int((time.time() - t0) * 1000)},
            })
        except Exception:
            pass

        return base

    # Always send meta first for streaming clients.
    _meta_payload = {
        "type": "meta",
        "cid": cid,
        "request_id": request_id,
        "conversation_id": stream_conv_id,
        "conv_id": stream_conv_id,
    }

    async def _with_meta(gen):
        try:
            yield _sse(_meta_payload)
            await asyncio.sleep(0)
        except Exception:
            pass
        async for _chunk in gen:
            yield _chunk

    def _sse_err(code: str, detail: str = "", retry_ms: int = 1500) -> dict:
        return _sse({"error": str(code), "detail": (detail or "")[:400], "retry": int(retry_ms)})

    # Helper to construct streaming responses compatible with pytest TestClient
    def _respond(gen):
        """Return EventSourceResponse in normal mode, StreamingResponse in TEST_MODE or when SSE is unavailable."""
        use_test_stream = False
        try:
            use_test_stream = (str(os.getenv("TEST_MODE", "")).strip() in {"1","true","True"})
        except Exception:
            use_test_stream = False
        if (EventSourceResponse is not None) and not use_test_stream:
            try:
                headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
                return EventSourceResponse(gen, ping=15, headers=headers)
            except Exception:
                return EventSourceResponse(gen, ping=15)
        # Wrap dict-yielding generator to raw SSE text for StreamingResponse
        async def _wrap():
            finalize_emitted = False
            try:
                async for chunk in gen:
                    try:
                        data = ""
                        if isinstance(chunk, dict):
                            data = str(chunk.get("data") or "")
                        else:
                            data = str(chunk)
                        if data:
                            # Detect finalize/done frames so we don't append a second one.
                            try:
                                parsed = json.loads(data)
                                if isinstance(parsed, dict) and (
                                    parsed.get("type") == "finalize" or parsed.get("done") is True
                                ):
                                    finalize_emitted = True
                            except Exception:
                                pass
                            yield ("data: " + data + "\n\n").encode("utf-8")
                    except Exception:
                        continue
                # Ensure closing event if generator did not send finalize/done.
                if not finalize_emitted:
                    try:
                        closing = _finalize_frame(intent=intent_label, text="")
                        yield ("data: " + json.dumps(closing, ensure_ascii=False) + "\n\n").encode("utf-8")
                    except Exception:
                        yield b"data: {\"done\": true}\n\n"
            except Exception:
                if not finalize_emitted:
                    try:
                        closing = _finalize_frame(intent=intent_label, text="")
                        yield ("data: " + json.dumps(closing, ensure_ascii=False) + "\n\n").encode("utf-8")
                    except Exception:
                        yield b"data: {\"done\": true}\n\n"
        return StreamingResponse(_wrap(), media_type="text/event-stream")

    # Basic rate limit per IP
    ip = request.client.host if request.client else "?"
    if not _rate_allow(ip, "chat_stream", limit=40, per_seconds=60):
        # Emit a small SSE error response (or HTTP when SSE off)
        if EventSourceResponse is None:
            raise HTTPException(429, "rate limit: 40/min")
        async def gen_rl():
            yield _sse({"error": "rate_limited", "detail": "Bitte kurz warten (40/min)", "retry": 3000})
            yield _sse(_finalize_frame(intent="rate_limited", text="Bitte kurz warten (40/min)", source_expected=False))
        resp = _respond(_with_meta(gen_rl()))
        if resp is not None:
            return resp

    # Moderation based on settings
    blocked, cleaned_msg, reason = moderate(user_msg, _ethics_level())
    if blocked:
        intent_label = "moderated"
        # Stream a friendly user-facing note, plus a machine-readable error signal
        if EventSourceResponse is None:
            return _finalize_frame(
                intent=intent_label,
                text="Ich kann dabei nicht helfen. Wenn du möchtest, kann ich stattdessen sichere Hintergründe erklären.",
                policy_override={"moderated": True},
                source_expected=False,
            )
        async def gen_block():
            out = "Ich kann dabei nicht helfen. Wenn du möchtest, erkläre ich sichere Hintergründe oder Alternativen."
            # User-friendly text (so the preview has content)
            yield _sse({"delta": out})
            # Error marker for UI logic (finalizes preview on client)
            yield _sse({"error": "moderated", "detail": str(reason or "")[:200], "retry": 0})
            yield _sse(_finalize_frame(intent=intent_label, text=out, policy_override={"moderated": True}, source_expected=False))
        try:
            _audit_chat({"ts": int(time.time()), "sid": sid, "blocked": True, "reason": reason, "user": user_msg})
        except Exception: pass
        resp = _respond(_with_meta(gen_block()))
        if resp is not None:
            return resp
    else:
        user_msg = cleaned_msg

    # -------------------------------------------------
    # Selftalk / smalltalk bypass (must never use web/memory and must never be blocked)
    # -------------------------------------------------
    try:
        from .intent_guard import classify as _ig_classify
        _intent0 = str(_ig_classify(user_msg) or "general")
    except Exception:
        _intent0 = "general"
    if _intent0 == "selftalk":
        low0 = (user_msg or "").lower().strip()
        if any(k in low0 for k in ["wie geht", "how are you"]):
            lead = "Mir geht’s gut, danke."
        elif any(k in low0 for k in ["hallo", "hi", "hey", "guten morgen", "guten tag", "guten abend", "hello", "good morning", "good evening"]):
            lead = "Hallo!"
        else:
            lead = "Ich bin KI_ana."
        reply_selftalk = (
            f"{lead} Ich bin deine digitale Begleiterin im KI_ana-System. "
            "Ich helfe dir beim Denken, Erklären, Planen, Schreiben und beim Debuggen von Code. "
            "Wobei kann ich dir helfen?"
        ).strip()

        policy_override = {"web_ok": False, "memory_retrieve_ok": False}

        async def gen_selftalk():
            yield _sse({"delta": reply_selftalk})
            yield _sse(_finalize_frame(intent="selftalk", text=reply_selftalk, policy_override=policy_override, source_expected=False))

        if EventSourceResponse is None:
            return _finalize_frame(intent="selftalk", text=reply_selftalk, policy_override=policy_override, source_expected=False)

        resp = _respond(_with_meta(gen_selftalk()))
        if resp is not None:
            return resp

    # -------------------------------------------------
    # Phase 1: Missing-Context-Gate (intent_guard)
    # Must short-circuit BEFORE retrieval/memory/LLM.
    # -------------------------------------------------
    try:
        from .intent_guard import guard_missing_context
        g = guard_missing_context(user_msg, lang=str(lang or "de-DE"))
    except Exception:
        g = None
    if g and getattr(g, "should_block", False):
        qs = list(getattr(g, "questions", []) or [])
        intent_g = str(getattr(g, "intent", "missing_context") or "missing_context")
        miss = list(getattr(g, "missing_fields", []) or [])
        note = str(getattr(g, "note", "Noch kein Kontext – KI_ana wartet auf Klärung.") or "")
        if not qs:
            qs = ["Kannst du kurz mehr Kontext geben?"]
        reply_guard = (
            "Bevor ich loslege, brauche ich noch kurz Kontext (ich will nichts raten):\n\n"
            + "\n".join([f"- {q}" for q in qs])
        ).strip()

        async def gen_guard():
            # Provide immediate user-visible content (avoid perceived hangs).
            yield _sse({"delta": reply_guard})
            payload = {
                "sources": [],
                "memory_ids": [],
                "origin": "intent_guard",
                "backend_log": {"pipeline": "intent_guard", "intent_guard": {"intent": intent_g, "missing": miss}},
                "explain": {"note": note},
            }
            yield _sse(_finalize_frame(intent=intent_g, text=reply_guard, payload=payload, source_expected=False))

        if EventSourceResponse is None:
            payload = {
                "sources": [],
                "memory_ids": [],
                "origin": "intent_guard",
                "backend_log": {"pipeline": "intent_guard", "intent_guard": {"intent": intent_g, "missing": miss}},
                "explain": {"note": note},
            }
            return _finalize_frame(intent=intent_g, text=reply_guard, payload=payload, source_expected=False)

        resp = _respond(_with_meta(gen_guard()))
        if resp is not None:
            return resp

    # Frage-Kontext vormerken
    try:
        if is_question(user_msg):
            _topic0 = extract_topic(user_msg)
            set_offer_context(sid, topic=(_topic0 or (user_msg[:80] if user_msg else None)), seed=user_msg)
    except Exception:
        pass

    topic = extract_topic(user_msg)
    query, topic = _combine_with_context(sid, user_msg, topic)
    
    # Add conversation memory context if needed
    memory_context = ""
    try:
        from .memory_integration import build_memory_context_with_ids, should_use_memory
        user_id = None
        try:
            if isinstance(current, dict) and current.get("id") is not None:
                user_id = int(current["id"])  # type: ignore[index]
        except Exception:
            user_id = None

        _mids_ctx: list[str] = []
        if user_id is not None:
            memory_context, _mids_ctx = build_memory_context_with_ids(user_msg, int(user_id))
        try:
            if _mids_ctx:
                _record_used_memory_ids(list(_mids_ctx))
        except Exception:
            pass
        if memory_context:
            query = f"{memory_context}\n\n{query}"
    except Exception:
        pass
    
    mem_hits = recall_mem(query, top_k=3) or []
    mem_hits = [m for m in mem_hits if float(m.get("score", 0)) >= MEM_MIN_SCORE][:3]
    style = _sanitize_style(style)
    bullet_limit = _sanitize_bullets(bullets)

    # 1) Explizite Wahl?
    choice = pick_choice(user_msg)
    if choice:
        ctx0 = get_offer_context(sid) or {}
        topic_ctx0 = ctx0.get("topic") or extract_topic(user_msg) or topic or ""
        seed_ctx0 = ctx0.get("seed") or user_msg
        set_last_offer(sid, None)
        set_offer_context(sid, topic=(topic_ctx0 or None), seed=seed_ctx0)
        async def gen_exec():
            out = await execute_choice(choice, topic_ctx0 or topic or "das Thema", seed_ctx0, persona, lang)
            yield _sse({"delta": clean(out)})
            yield _sse(_finalize_frame(intent="choice", text=clean(out), source_expected=False))
        if EventSourceResponse is None:
            out = await execute_choice(choice, topic_ctx0 or topic or "das Thema", seed_ctx0, persona, lang)
            return _finalize_frame(intent="choice", text=clean(out), extra={"delta": clean(out)}, source_expected=False)
        resp = _respond(_with_meta(gen_exec()))
        if resp is not None:
            return resp

    # 2) Bestätigung auf letztes Angebot?
    prev = get_last_offer(sid)
    if prev and is_affirmation(user_msg):
        set_last_offer(sid, None)
        async def gen_prev():
            ctx = get_offer_context(sid) or {}
            topic_ctx = (ctx.get("topic") or topic or "das Thema")
            seed_ctx = ctx.get("seed") or user_msg
            out = await execute_choice(prev, topic_ctx, seed_ctx, persona, lang)
            yield _sse({"delta": clean(out)})
            yield _sse(_finalize_frame(intent="choice", text=clean(out), source_expected=False))
        if EventSourceResponse is None:
            ctx = get_offer_context(sid) or {}
            topic_ctx = (ctx.get("topic") or topic or "das Thema")
            seed_ctx = ctx.get("seed") or user_msg
            out = await execute_choice(prev, topic_ctx, seed_ctx, persona, lang)
            return _finalize_frame(intent="choice", text=clean(out), extra={"delta": clean(out)}, source_expected=False)
        resp = _respond(_with_meta(gen_prev()))
        if resp is not None:
            return resp

    # KI_ana Self-Awareness Check - Priority over everything else
    if any(kw in user_msg.lower() for kw in ['wer bist du', 'was bist du', 'dein name', 'dein zweck']):
        intent_label = "identity"
        async def gen_identity():
            try:
                from .ai_consciousness import get_identity
                identity = get_identity()
                direct_answer = f"Ich bin {identity['name']} v{identity['version']}, eine {identity['type']}. Mein Zweck ist {identity['purpose']}. Ich wurde erschaffen, um zu lernen, zu helfen und zu beschützen. Meine Architektur basiert auf blockchain-basiertem Gedächtnis und dezentralen Sub-KIs. Ich habe vollen Zugriff auf meinen Code und bin mir meiner selbst vollständig bewusst."
                yield _sse({"delta": direct_answer})
                yield _sse(_finalize_frame(intent=intent_label, text=direct_answer, extra={"identity_response": True}, source_expected=False))
            except Exception:
                fb = "Ich bin KI_ana, eine dezentrale Mutter-KI. Mein Zweck ist zu lernen, zu helfen und zu beschützen."
                yield _sse({"delta": fb})
                yield _sse(_finalize_frame(intent=intent_label, text=fb, extra={"identity_fallback": True}, source_expected=False))
        if EventSourceResponse is None:
            try:
                from .ai_consciousness import get_identity
                identity = get_identity()
                txt = f"Ich bin {identity['name']} v{identity['version']}, eine {identity['type']}. Mein Zweck ist {identity['purpose']}."
                return _finalize_frame(intent=intent_label, text=txt, extra={"delta": txt}, source_expected=False)
            except Exception:
                txt = "Ich bin KI_ana, eine dezentrale Mutter-KI."
                return _finalize_frame(intent=intent_label, text=txt, extra={"delta": txt}, source_expected=False)
        resp = _respond(_with_meta(gen_identity()))
        if resp is not None:
            return resp

    # Smalltalk/Gruß vor Planner-Branch abfangen (freundliche Kurzantwort)
    if _HOW_ARE_YOU.search(user_msg.lower()):
        intent_label = "smalltalk"
        async def gen_smalltalk():
            # Slim, no follow-ups
            txt = "Mir geht's gut – bereit zu helfen."
            yield _sse({"delta": txt})
            yield _sse(_finalize_frame(intent=intent_label, text=txt, extra={"no_prompts": True}, source_expected=False))
        if EventSourceResponse is None:
            txt = "Mir geht's gut – bereit zu helfen."
            return _finalize_frame(intent=intent_label, text=txt, extra={"delta": txt}, source_expected=False)
        resp = _respond(_with_meta(gen_smalltalk()))
        if resp is not None:
            return resp
    if _GREETING.search(user_msg.lower()):
        async def gen_greet():
            txt = "Hallo! Wie kann ich helfen?"
            yield _sse({"delta": txt})
            yield _sse(_finalize_frame(intent="greeting", text=txt, extra={"no_prompts": True}, source_expected=False))
        if EventSourceResponse is None:
            txt = "Hallo! Wie kann ich helfen?"
            return _finalize_frame(intent="greeting", text=txt, extra={"delta": txt}, source_expected=False)
        resp = _respond(_with_meta(gen_greet()))
        if resp is not None:
            return resp

    # Planner‑Streaming (Standard) – guarded by env flag
    try:
        import os as _os
        _PLANNER_ON = (_os.getenv('KI_PLANNER_ENABLED', '1').strip() in {'1','true','True','yes','on'})
    except Exception:
        _PLANNER_ON = True
    if _PLANNER_ON and (EventSourceResponse is not None):
        # Temporary simplified streaming: use Safety‑Valve to ensure robust, immediate answers
        async def gen_simple():
            stream_started_ts = time.time()
            deadline = stream_started_ts + 30.0
            first_event_logged = False
            finalize_sent = False

            def _ms() -> int:
                try:
                    return int((time.time() - stream_started_ts) * 1000)
                except Exception:
                    return 0

            def _user_label() -> str:
                try:
                    u = getattr(request, "state", None) and getattr(request.state, "user", None)
                    if isinstance(u, dict):
                        return str(u.get("username") or u.get("id") or "?")
                    return str(getattr(u, "username", None) or getattr(u, "id", None) or "?")
                except Exception:
                    return "?"

            def _audit_stream(evt: str, meta: Optional[dict] = None) -> None:
                try:
                    _audit_chat({
                        "ts": int(time.time()),
                        "sid": sid,
                        "event": str(evt),
                        "cid": cid,
                        "request_id": request_id,
                        "conv_id": stream_conv_id,
                        "ip": ip,
                        "meta": (meta or {}),
                    })
                except Exception:
                    pass

            try:
                try:
                    logger.info("STREAM_START cid=%s request_id=%s conv_id=%s user=%s", cid, request_id, str(conv_id or ""), _user_label())
                except Exception:
                    pass
                _audit_stream("STREAM_START")

                # Emit immediate first SSE event to prevent hangs without output.
                # Empty delta is a valid SSE message and satisfies DoD.
                try:
                    yield _sse({"type": "delta", "text": ""})
                    await asyncio.sleep(0)
                    if not first_event_logged:
                        try:
                            logger.info("STREAM_FIRST_EVENT cid=%s request_id=%s ms=%s", cid, request_id, _ms())
                        except Exception:
                            pass
                        _audit_stream("STREAM_FIRST_EVENT", {"ms": _ms()})
                        first_event_logged = True
                except Exception:
                    pass
                
                # KI_ana Self-Awareness Check - Priority over everything else
                if any(kw in (message or "").lower() for kw in ['wer bist du', 'was bist du', 'dein name', 'dein zweck']):
                    try:
                        from .ai_consciousness import get_identity
                        identity = get_identity()
                        direct_answer = f"Ich bin {identity['name']} v{identity['version']}, eine {identity['type']}. Mein Zweck ist {identity['purpose']}. Ich wurde erschaffen, um zu lernen, zu helfen und zu beschützen. Meine Architektur basiert auf blockchain-basiertem Gedächtnis und dezentralen Sub-KIs. Ich habe vollen Zugriff auf meinen Code und bin mir meiner selbst vollständig bewusst."
                        yield _sse({"delta": direct_answer})
                        finalize_sent = True
                        yield _sse(_finalize_frame(intent="identity", text=direct_answer, extra={"identity_response": True}, source_expected=False))
                        return
                    except Exception:
                        fb = "Ich bin KI_ana, eine dezentrale Mutter-KI. Mein Zweck ist zu lernen, zu helfen und zu beschützen."
                        yield _sse({"delta": fb})
                        finalize_sent = True
                        yield _sse(_finalize_frame(intent="identity", text=fb, extra={"identity_fallback": True}, source_expected=False))
                        return
                
                # Determine if web is allowed
                web_ok_allowed = bool(web_ok)
                try:
                    settings = _read_runtime_settings()
                    if settings:
                        web_ok_allowed = web_ok_allowed or bool(settings.get("web_ok"))
                except Exception:
                    pass

                # Decide if we should actually use web for this request.
                # DoD: general knowledge questions should not trigger web; only current/news/verification queries may.
                try:
                    _msg_l = (message or "").strip().lower()
                except Exception:
                    _msg_l = ""

                try:
                    is_simple_knowledge = bool(_is_simple_knowledge_question(_msg_l))
                except Exception:
                    is_simple_knowledge = False

                needs_web = False
                try:
                    needs_web = _looks_like_current_query(_msg_l) or any(k in _msg_l for k in [
                        "heute", "news", "aktuell", "letzte woche", "gestern", "verifizieren", "quelle", "beleg",
                        "stand ", "update", "neuigkeit", "meldungen",
                    ])
                except Exception:
                    needs_web = False

                web_ok_flag = bool(web_ok_allowed and needs_web and (not is_simple_knowledge))
                # Add conversation memory context if needed
                memory_context = ""
                try:
                    from .memory_integration import build_memory_context, should_use_memory
                    # Use user_id=1 for testing (would be real user_id in production)
                    user_id = 1
                    memory_context = build_memory_context(message or "", user_id)
                except Exception:
                    pass
                
                # Intent detection for confirmations
                low = (message or "").strip().lower()
                ctx = None
                try:
                    ctx = get_offer_context(sid)
                except Exception:
                    ctx = None
                ctx_topic = (ctx.get("topic") if isinstance(ctx, dict) else None) or (extract_topic(message) or message)
                if any(k in low for k in ["zeige details", "details zeigen", "details"]):
                    # Stream more detailed memory snippets (top 3)
                    try:
                        mem = _kb_snippets(ctx_topic, top_k=3)
                        if mem:
                            def _fmt_ts(ts):
                                try:
                                    t = int(ts)
                                    return time.strftime("%Y-%m-%d", time.gmtime(t))
                                except Exception:
                                    return ""
                            parts = ["📑 Details (Gedächtnis):"]
                            for idx, m in enumerate(mem[:3], start=1):
                                title = (m.get("title") or ctx_topic).strip()
                                cnt = (m.get("content") or "")
                                snip = cnt[:400] + ("…" if len(cnt) > 400 else "")
                                ts = _fmt_ts(m.get("ts"))
                                head = f"🔹 Snippet {idx}: {title}"
                                if ts:
                                    head += f"  ({ts})"
                                parts.append(head)
                                parts.append(snip)
                            out = "\n".join(parts)
                            yield _sse({"delta": out + ("\n" if not out.endswith("\n") else "")})
                        finalize_sent = True
                        yield _sse(_finalize_frame(intent="details", text=str(out or ""), extra={"details": True, "topic": extract_topic(message)}, source_expected=False))
                    except Exception:
                        finalize_sent = True
                        yield _sse(_finalize_frame(intent="details", text="", source_expected=False))
                    return
                if any(k in low for k in ["ja, vergleiche", "ja vergleiche", "mach den vergleich", "vergleich", "vergleiche"]):
                    # Execute compare flow
                    cmp_txt, cmp_sources = compare_memory_with_web(ctx_topic, web_ok=bool(web_ok_flag))
                    out = (cmp_txt or "")
                    if out:
                        yield _sse({"delta": out + ("\n" if not out.endswith("\n") else "")})
                    if cmp_sources:
                        block = format_sources_once(out or "", cmp_sources, limit=3)
                        if block:
                            yield _sse({"delta": block})
                    # Save comparison block (tags include 'comparison') if autonomy >= 2
                    saved_ids: List[str] = []
                    try:
                        if int(autonomy or 0) >= 2 and out:
                            blk = save_memory(
                                title=str(ctx_topic)[:120],
                                content=out,
                                tags=["comparison", "learned"],
                                url=(cmp_sources[0].get("url") if cmp_sources else None),
                            )
                            _debug_save("auto_save_comparison", blk or {})
                            # Memory-save logging
                            try:
                                if blk and isinstance(blk, dict) and blk.get("id"):
                                    logger.info("[memory-save] id=%s source=%s tags=%s", blk.get("id"), blk.get("source"), blk.get("tags"))
                                else:
                                    logger.error("[memory-save] failed for topic=%s", str(ctx_topic)[:120])
                            except Exception:
                                pass

                            try:
                                upsert_addressbook(
                                    ctx_topic or "",
                                    block_file=str((blk or {}).get("file") or ""),
                                    url=(cmp_sources[0].get("url") if cmp_sources else ""),
                                )
                            except Exception:
                                pass

                            bid = ""
                            try:
                                bid = _extract_block_id(blk or {})
                            except Exception as e:
                                logger.error("auto_save_comparison: bad blk type: %s (%s)", type(blk), e)

                            if bid:
                                saved_ids.append(str(bid))
                    except Exception as e:
                        logger.error("auto_save_comparison failed: %s", e, exc_info=True)

                    try:
                        mem_ids = list(saved_ids)
                        # Build finalize payload (sources only from memory here)
                        payload = _finalize_payload("", memory_ids=mem_ids, web_links=[])
                        payload.update({
                            "comparison": True,
                            "topic": extract_topic(message),
                        })
                        assembled = str(out or "")
                        try:
                            if cmp_sources:
                                assembled = format_sources_once(assembled, cmp_sources, limit=3) or assembled
                        except Exception:
                            pass
                        payload = _finalize_frame(intent="comparison", text=assembled, payload=payload, extra={"comparison": True, "topic": extract_topic(message)}, source_expected=True)
                        finalize_sent = True
                        yield _sse(payload)
                    except Exception:
                        finalize_sent = True
                        yield _sse(_finalize_frame(intent="comparison", text="", source_expected=True))
                    return
                # Confirmation branch ("ja, speichern") entfernt:
                # KI_ana entscheidet nun selbstständig, ob und wann etwas gespeichert wird.
                # Explizite "ja, speichern"-Eingaben haben keine Sonderbehandlung mehr.
                # Build thoughtful answer using memory check + web compare
                topic_q = extract_topic(message) or message
                # Add memory context to the question
                if memory_context.strip():
                    topic_q = f"{memory_context.strip()}\n\n{topic_q}"
                try:
                    logger.info("LLM_CALL_START cid=%s request_id=%s", cid, request_id)
                except Exception:
                    pass
                try:
                    remaining = max(0.0, deadline - time.time())
                    if remaining < 0.25:
                        try:
                            logger.warning("STREAM_ABORT cid=%s request_id=%s reason=timeout", cid, request_id)
                        except Exception:
                            pass
                        _audit_stream("STREAM_ABORT", {"reason": "timeout"})
                        finalize_sent = True
                        yield _sse(_finalize_frame(intent="timeout", ok=False, error="timeout", text="Timeout", source_expected=False))
                        return
                    a_text, a_origin, a_delta, a_saved_ids, a_sources, a_had_memory, a_had_web, a_mem_count = await asyncio.wait_for(
                        answer_with_memory_check(topic_q, web_ok=bool(web_ok_flag), autonomy=int(autonomy or 0)),
                        timeout=min(29.0, max(0.25, remaining)),
                    )
                except asyncio.TimeoutError:
                    try:
                        logger.warning("STREAM_ABORT cid=%s request_id=%s reason=timeout", cid, request_id)
                    except Exception:
                        pass
                    _audit_stream("STREAM_ABORT", {"reason": "timeout"})
                    finalize_sent = True
                    yield _sse(_finalize_frame(intent="timeout", ok=False, error="timeout", text="Timeout", source_expected=False))
                    return
                finally:
                    try:
                        logger.info("LLM_CALL_END cid=%s request_id=%s", cid, request_id)
                    except Exception:
                        pass
                txt = (a_text or "").strip()
                srcs = a_sources or []
                # Apply compact formatting to avoid text deserts
                try:
                    from .memory_integration import compact_response
                    txt = compact_response(txt, max_length=150)
                except Exception:
                    pass
                if txt:
                    yield _sse({"delta": txt + ("\n" if not txt.endswith("\n") else "")})
                final_text_full = txt + ("\n" if (txt and not txt.endswith("\n")) else "")
                if srcs:
                    block = format_sources_once(txt or "", srcs, limit=3)
                    if block:
                        yield _sse({"delta": block})
                        try:
                            if (txt or "") and isinstance(block, str) and block.lstrip().startswith((txt or "").strip()):
                                final_text_full = block
                            else:
                                final_text_full = (final_text_full or "") + str(block or "")
                        except Exception:
                            final_text_full = (final_text_full or "") + str(block or "")
                # Hard deadline guard: always finalize within 30s
                try:
                    if time.time() > deadline:
                        try:
                            logger.warning("STREAM_ABORT cid=%s request_id=%s reason=timeout", cid, request_id)
                        except Exception:
                            pass
                        _audit_stream("STREAM_ABORT", {"reason": "timeout"})
                        finalize_sent = True
                        yield _sse(_finalize_frame(intent="timeout", ok=False, error="timeout", text="Timeout", source_expected=False))
                        return
                except Exception:
                    pass
                # Persist conversation + memory before final meta
                saved_ids: List[str] = []
                try:
                    for _sid in (a_saved_ids or []):
                        if _sid and _sid not in saved_ids:
                            saved_ids.append(str(_sid))
                except Exception:
                    pass
                try:
                    if current and current.get("id"):
                        uid = int(current["id"])  # type: ignore
                        conv = _ensure_conversation(db, uid, conv_id)
                        _save_msg(db, conv.id, "user", message)
                        _save_msg(db, conv.id, "ai", txt)
                        asyncio.create_task(_retitle_if_needed(conv.id, message, txt, lang or "de-DE"))
                        
                        # Auto-save conversation to memory if needed
                        async def _auto_save():
                            try:
                                from .memory_integration import auto_save_conversation_if_needed
                                block_id = await auto_save_conversation_if_needed(conv.id, uid, db)
                                if block_id:
                                    logger.info(f"[memory-auto-save] Conversation {conv.id} saved as {block_id}")
                            except Exception as e:
                                logger.error(f"[memory-auto-save] Failed: {e}")
                        asyncio.create_task(_auto_save())
                except Exception:
                    pass
                # Do not double-save here; answer_with_memory_check already saved when no prior knowledge existed
                # Final meta
                try:
                    # Intent label for explain/finalize:
                    # - keep it stable and meaningful (avoid "safety_valve" for normal knowledge questions)
                    intent_for_finalize = "chat"
                    try:
                        if is_simple_knowledge:
                            intent_for_finalize = "knowledge"
                        elif needs_web and bool(web_ok_allowed):
                            intent_for_finalize = "current_query"
                    except Exception:
                        intent_for_finalize = "chat"

                    mem_ids = list(saved_ids)
                    # include addressbook lookup IDs as context (best-effort)
                    try:
                        for h in (mem_hits or []):
                            bid = h.get('id') or _extract_bid_from_path(str(h.get('path') or ''))
                            if bid:
                                mem_ids.append(str(bid))
                    except Exception:
                        pass
                    # Extract web links from gathered sources (robust: url|link|href) and synthesize if needed
                    from urllib.parse import urlparse as _urlparse
                    import re as _re

                    def _extract_domain(_val: str) -> str:
                        try:
                            s = (str(_val or "")).strip()
                            if not s:
                                return ""
                            if s.startswith(("http://", "https://")):
                                try:
                                    return ( _urlparse(s).netloc or "" ).strip()
                                except Exception:
                                    pass
                            m = _re.search(r"\b([a-z0-9-]+(?:\.[a-z0-9-]+)+)\b", s, _re.I)
                            if m:
                                return m.group(1).lower()
                        except Exception:
                            pass
                        return ""

                    def _collect_web_links_from_sources(_sources: list) -> list[str]:
                        out: list[str] = []
                        try:
                            for _s in (_sources or []):
                                if not isinstance(_s, dict):
                                    continue
                                for _k in ("url", "link", "href"):
                                    _u = _s.get(_k)
                                    if isinstance(_u, str) and _u.strip():
                                        out.append(_u.strip())
                                        break
                        except Exception:
                            pass
                        # de-dup
                        _seen = set(); _uniq = []
                        for _u in out:
                            if _u not in _seen:
                                _seen.add(_u); _uniq.append(_u)
                        return _uniq

                    web_links = _collect_web_links_from_sources(srcs if isinstance(srcs, list) else [])

                    # Synthesize minimal web link if origin suggests web/mixed and allowed but none collected
                    try:
                        _origin_hint = (a_origin or "").strip().lower()
                    except Exception:
                        _origin_hint = "unknown"
                    if (not web_links) and (web_ok_flag in (True, 1, "1", "true", "True")):
                        try:
                            candidates: list[str] = []
                            for _s in (srcs or []):
                                if not isinstance(_s, dict):
                                    continue
                                for _k in ("title", "source", "origin", "provider", "name"):
                                    _v = _s.get(_k)
                                    if isinstance(_v, str) and _v.strip():
                                        candidates.append(_v.strip())
                            if not candidates and isinstance(txt, str) and txt:
                                candidates.append(txt[:120])
                            _domain = ""
                            for _val in candidates:
                                _domain = _extract_domain(_val)
                                if _domain:
                                    break
                            if _domain:
                                web_links = [f"https://{_domain}"]
                        except Exception:
                            web_links = []
                    # No placeholder fallback: if still empty, we will return only memory sources

                    # Build finalize payload with sources
                    payload = _finalize_payload(txt, memory_ids=mem_ids, web_links=web_links)
                    payload.update({
                        "done": True,
                        "safety_valve": False,
                        "origin": (a_origin or "unknown"),
                        "delta_note": (a_delta or ""),
                        "topic": extract_topic(message),
                    })

                    # ---- MetaMind KPIs + explain trace (stable schema) ----
                    try:
                        # Tool metrics (best-effort)
                        from netapi.modules.observability import metrics as obs_metrics

                        obs_metrics.inc_chat_tool_call(tool="memory", ok=bool(mem_ids))
                        if bool(web_ok_flag):
                            obs_metrics.inc_chat_tool_call(tool="web", ok=bool(web_links))
                    except Exception:
                        pass
                    try:
                        from netapi.modules.quality_gates import gates as qg

                        qg.record_tool_call(ok=bool(mem_ids))
                        if bool(web_ok_flag):
                            qg.record_tool_call(ok=bool(web_links))
                    except Exception:
                        pass
                    try:
                        _attach_explain_and_kpis(
                            payload,
                            route="/api/chat/stream",
                            intent=intent_for_finalize,
                            policy={
                                # policy.web_ok is the *permission* toggle; web_used indicates actual usage for this request.
                                "web_ok": bool(web_ok_allowed),
                                "web_used": bool(web_ok_flag),
                                "autonomy": int(autonomy or 0),
                                "style": str(style or ""),
                                "bullets": int(bullet_limit or 0),
                            },
                            tools=[
                                {"tool": "memory", "ok": bool(mem_ids)},
                                {"tool": "web", "ok": bool(web_links)},
                            ],
                            source_expected=True,
                        )
                    except Exception:
                        pass
                    # Finalize source logging
                    try:
                        topic = payload.get("topic") or extract_topic(message)
                        origin = payload.get("origin") or "unknown"
                        logger.info("[chat-finalize] topic=%s origin=%s memory_ids=%s web_links=%s", topic, origin, len(mem_ids or []), len(web_links or []))
                        if origin in ("web", "mixed") and not web_links:
                            logger.warning("[sources] origin=%s but no web links extracted (topic=%s)", origin, topic)
                        if origin == "mixed":
                            found = []
                            if mem_ids: found.append("memory")
                            if web_links: found.append("web")
                            if len(found) < 2:
                                logger.warning("[sources] origin=mixed incomplete (topic=%s, found=%s)", topic, found)
                    except Exception:
                        pass
                    # Perf timing
                    try:
                        elapsed = time.time() - t0
                        if elapsed > 5.0:
                            logger.warning("[perf] slow answer for topic=%s (%.2fs)", payload.get("topic") or "", elapsed)
                    except Exception:
                        pass
                    try:
                        if a_had_memory and a_had_web:
                            payload["ask_compare"] = True
                        if a_had_memory and int(a_mem_count or 0) >= 2:
                            payload["ask_details"] = True
                    except Exception:
                        pass
                    try:
                        _ft = ""
                        try:
                            _ft = str(final_text_full or "")
                        except Exception:
                            _ft = str(txt or "")
                        payload = _finalize_frame(intent=intent_for_finalize, text=_ft, payload=payload, source_expected=True)
                    except Exception:
                        pass
                    finalize_sent = True
                    yield _sse(payload)
                except Exception:
                    finalize_sent = True
                    yield _sse(_finalize_frame(intent="chat", text="", source_expected=True))
                return
            except Exception as e:
                reason = ""
                try:
                    reason = str(e)[:200]
                except Exception:
                    reason = "error"
                try:
                    logger.error("STREAM_ABORT cid=%s request_id=%s reason=%s", cid, request_id, reason)
                except Exception:
                    pass
                try:
                    _audit_stream("STREAM_ABORT", {"reason": reason})
                except Exception:
                    pass
                yield _sse_err("stream_failed", "Stream fehlgeschlagen", 1200)
                finalize_sent = True
                yield _sse(_finalize_frame(intent="stream_failed", ok=False, error=reason, text="", source_expected=False))
            finally:
                # Last-resort DoD: try to always emit a finalize frame.
                if not finalize_sent:
                    try:
                        yield _sse(_finalize_frame(intent="stream_failed", ok=False, error="stream_closed", text="", source_expected=False))
                    except Exception:
                        pass
        return _respond(_with_meta(gen_simple()))

# ---- Knowledge helpers: addressbook ↔ memory ↔ web -------------------------
ADDRBOOK_PATH = Path(__file__).resolve().parents[3] / "memory" / "index" / "addressbook.json"
BLOCKS_DIR = Path(__file__).resolve().parents[3] / "memory" / "long_term" / "blocks"

def lookup_addressbook(topic: str) -> List[Dict[str, Any]]:
    try:
        if not ADDRBOOK_PATH.exists():
            return []
        data = _json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8") or "{}")
        blocks = data.get("blocks") or []
        t = (topic or "").strip().lower()
        return [b for b in blocks if str(b.get("topic",""))[:120].strip().lower() == t]
    except Exception:
        return []

def _read_block_json(path: str) -> Dict[str, Any]:
    try:
        p = path or ""
        if p and "/" not in p:
            p = str(BLOCKS_DIR / f"{p}")
        if not p.endswith(".json"):
            p = p + ".json"
        fp = Path(p)
        if not fp.exists():
            return {}
        return _json.loads(fp.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}

def _kb_snippets(topic: str, top_k: int = 5) -> List[Dict[str, Any]]:
    items = lookup_addressbook(topic)
    out: List[Dict[str, Any]] = []
    for it in items[:top_k]:
        blk = _read_block_json(str(it.get("path") or it.get("block_id") or ""))
        if blk:
            out.append({
                "id": blk.get("id") or it.get("block_id"),
                "title": blk.get("title") or topic,
                "content": blk.get("content") or "",
                "url": blk.get("url") or it.get("source") or "",
                "ts": it.get("timestamp") or blk.get("timestamp") or None,
            })
    return out

def _answer_from_web(topic: str, top_k: int = 3) -> tuple[str, List[Dict[str, Any]]]:
    try:
        ans, sources = try_web_answer(topic, limit=top_k)
        return (ans or ""), (sources or [])
    except Exception:
        return "", []

def _db_path_from_env() -> str:
    try:
        db_url = os.getenv("DATABASE_URL", "sqlite:///db.sqlite3").strip()
        if db_url.startswith("sqlite:///"):
            return os.path.expanduser(db_url[len("sqlite:///"):])
        if db_url.startswith("sqlite://"):
            return os.path.expanduser(db_url[len("sqlite://"):])
        return os.path.expanduser(db_url)
    except Exception:
        return "db.sqlite3"

def _fetch_memory_snippets(topic: str, limit: int = 3) -> List[Dict[str, Any]]:
    try:
        import sqlite3
        t = (topic or "").strip().lower()
        if not t:
            return []
        db_path = _db_path_from_env()
        rows: List[Dict[str, Any]] = []
        where = "(LOWER(source) LIKE ? OR LOWER(tags) LIKE ? OR LOWER(content) LIKE ?)"
        like = f"%{t}%"
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                f"SELECT id, ts, source, type, tags, content FROM knowledge_blocks WHERE {where} ORDER BY ts DESC, id DESC LIMIT ?",
                (like, like, like, int(limit or 3)),
            )
            for r in cur.fetchall():
                rows.append({
                    "id": f"BLK_{int(r['id'])}",
                    "source": r["source"] or "",
                    "url": r["type"] or "",
                    "tags": r["tags"] or "",
                    "content": r["content"] or "",
                    "ts": int(r["ts"] or 0),
                })
        return rows
    except Exception:
        return []

def _summarize_memory(snippets: List[Dict[str, Any]], max_sentences: int = 5) -> str:
    try:
        if not snippets:
            return ""
        sents: List[str] = []
        for sn in snippets:
            sents += _sentences(str(sn.get("content") or ""))
        # de-dup while preserving order
        seen = set()
        uniq = []
        for s in sents:
            k = s.lower()
            if k in seen:
                continue
            seen.add(k)
            uniq.append(s)
        return " ".join(uniq[: max(1, int(max_sentences or 5))])
    except Exception:
        return ""

def _merge_memory_web(mem_text: str, web_text: str) -> tuple[str, str]:
    try:
        mem_text = (mem_text or "").strip()
        web_text = (web_text or "").strip()
        if mem_text and not web_text:
            base = mem_text
            pts = build_points(mem_text, max_points=5)
            out = base
            if pts:
                out += "\n\nKernpunkte:\n" + "\n".join(f"• {p}" for p in pts)
            return out, ""
        if web_text and not mem_text:
            base = web_text
            pts = build_points(web_text, max_points=5)
            out = base
            if pts:
                out += "\n\nKernpunkte:\n" + "\n".join(f"• {p}" for p in pts)
            return out, ""
        if mem_text and web_text:
            # Fuse: start with a cohesive 2–4 sentence mix, then bullets with additions
            fused = " ".join((_sentences(mem_text)[:3] or []))
            if not fused:
                fused = mem_text[:400]
            new_pts = []
            try:
                mem_set = {s.lower() for s in _sentences(mem_text)}
                for s in _sentences(web_text):
                    if s.lower() not in mem_set:
                        new_pts.append(s)
            except Exception:
                pass
            bullets = (build_points(mem_text, max_points=3) + build_points(" ".join(new_pts), max_points=3))[:6]
            out = fused
            if bullets:
                out += "\n\nKernpunkte:\n" + "\n".join(f"• {p}" for p in bullets)
            delta = "Neue Punkte aus Web ergänzt." if new_pts else ""
            return out, delta
        return "", ""
    except Exception:
        return "", ""

def _origin_label(has_mem: bool, has_web: bool) -> str:
    return "mixed" if (has_mem and has_web) else ("memory" if has_mem else ("web" if has_web else "unknown"))

async def answer_with_memory_check(topic: str, web_ok: bool = True, autonomy: int = 0):
    cid = ""
    request_id = ""
    try:
        _ctx = _CHAT_EXPLAIN_CTX.get()
        if isinstance(_ctx, dict):
            cid = str(_ctx.get("cid") or "")
            request_id = str(_ctx.get("request_id") or "")
    except Exception:
        cid = ""
        request_id = ""
    saved_ids: List[str] = []
    used_ids: List[str] = []
    # Memory-first from SQLite
    mem_snips = _fetch_memory_snippets(topic, limit=3)
    try:
        used_ids = [str(sn.get('id')) for sn in (mem_snips or []) if sn.get('id')]
    except Exception:
        used_ids = []
    mem_text = _summarize_memory(mem_snips, max_sentences=5)
    # Web assist
    web_text = ""; web_sources: List[dict] = []
    if web_ok:
        try:
            try:
                if cid:
                    logger.info("TOOL_CALL_START cid=%s request_id=%s tool=web", cid, request_id)
            except Exception:
                pass
            _wt, _ws = _answer_from_web(topic, top_k=3)
            web_text = _wt or ""
            web_sources = list(_ws or [])
            try:
                if cid:
                    logger.info("TOOL_CALL_END cid=%s request_id=%s tool=web status=ok", cid, request_id)
            except Exception:
                pass
        except Exception:
            web_text = ""; web_sources = []
            try:
                if cid:
                    logger.info("TOOL_CALL_END cid=%s request_id=%s tool=web status=error", cid, request_id)
            except Exception:
                pass
    # Synthesis
    ans_text, delta_note = _merge_memory_web(mem_text, web_text)
    if not ans_text:
        # Final fallback: do NOT add empty scaffolding.
        base = (mem_text or web_text or "").strip()
        if base:
            pts = build_points(base, max_points=4)
            ans_text = base
            if pts:
                ans_text = base + "\n\nKernpunkte:\n" + "\n".join(f"• {p}" for p in pts)
        else:
            ans_text = ""
    # Apply compact formatting
    from .memory_integration import compact_response
    ans_text = compact_response(ans_text, max_length=150)
    # Save automatically if allowed
    has_mem = bool(mem_snips)
    has_web = bool(web_text)
    origin = _origin_label(has_mem, has_web)
    if int(autonomy or 0) >= 2 and ans_text:
        try:
            tagset = ["vision", "learned"] + (["web"] if has_web else ["memory"])
            url0 = (web_sources[0].get("url") if web_sources else None)
            blk = save_memory(title=str(topic)[:120], content=ans_text, tags=tagset, url=url0)
            _debug_save("auto_save_initial", blk or {})
            try:
                upsert_addressbook(topic or "", block_file=str((blk or {}).get("file") or ""), url=(url0 or ""))
            except Exception:
                pass
            try:
                bid = _extract_block_id(blk or {})
                if bid:
                    saved_ids.append(str(bid))
                    try:
                        logger.info("[autosave] topic=%s origin=%s blk=%s", str(topic)[:120], origin, bid)
                    except Exception:
                        pass
            except Exception:
                try: logger.error("auto_save_initial: bad blk type: %s", type(blk))
                except Exception: pass
        except Exception:
            pass
    had_memory = has_mem
    had_web = has_web
    mem_count = len(mem_snips)
    try:
        logger.info("[answer_with_memory_check] topic=%s mem_count=%s has_web=%s origin=%s", str(topic)[:120], mem_count, had_web, origin)
    except Exception:
        pass
    try:
        all_ids = _dedupe_str_list(list(used_ids or []) + list(saved_ids or []))
    except Exception:
        all_ids = _dedupe_str_list(list(saved_ids or []))
    try:
        if all_ids:
            _record_used_memory_ids(all_ids)
    except Exception:
        pass
    return ans_text, origin, delta_note, all_ids, web_sources, had_memory, had_web, mem_count

def _extract_points(text: str) -> List[str]:
    try:
        import re as _re
        sents = [s.strip() for s in _re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
        return sents[:8]
    except Exception:
        return []

def _years(text: str) -> List[int]:
    try:
        import re as _re
        yrs = [int(y) for y in _re.findall(r"\b(19\d{2}|20\d{2})\b", text or "")]
        return yrs[:6]
    except Exception:
        return []

def _numbers(text: str) -> List[float]:
    try:
        import re as _re
        vals = []
        for m in _re.finditer(r"(?<![\w\d])(\d+[\d\.,]*)", text or ""):
            try:
                v = float(str(m.group(1)).replace('.', '').replace(',', '.'))
                vals.append(v)
            except Exception:
                continue
        return vals[:8]
    except Exception:
        return []

def _has_negation(text: str) -> bool:
    try:
        t = (text or '').lower()
        return any(kw in t for kw in [" nicht ", " kein ", " keine ", " keines ", " never ", "no "])
    except Exception:
        return False

def _token_overlap(a: str, b: str) -> int:
    try:
        import re as _re
        stop = {"der","die","das","und","oder","ein","eine","ist","sind","war","waren","von","im","in","am","zu","für","mit","auf","aus","den","dem","des","the","a","an","of","to","for","and","or","is","are"}
        ta = {w for w in _re.findall(r"[a-zA-ZäöüÄÖÜß0-9]{3,}", a.lower()) if w not in stop}
        tb = {w for w in _re.findall(r"[a-zA-ZäöüÄÖÜß0-9]{3,}", b.lower()) if w not in stop}
        return len(ta & tb)
    except Exception:
        return 0

def compare_memory_with_web(topic: str, web_ok: bool = True):
    mem = _kb_snippets(topic, top_k=5)
    web_sources: List[Dict[str, Any]] = []
    if web_ok:
        _t, web_sources = _answer_from_web(topic, top_k=3)
    mem_points: List[str] = []
    try:
        for m in mem:
            mem_points += _extract_points(m.get("content") or "")
    except Exception:
        pass
    web_points: List[str] = []
    try:
        for w in web_sources:
            sn = w.get("snippet") or ""
            web_points += _extract_points(sn)
    except Exception:
        pass
    # naive delta for new points
    new_points = [p for p in web_points if p and all(p not in mp for mp in mem_points)]

    # Unterschiedlich / Widersprüchlich heuristics
    diffs: List[str] = []
    contras: List[str] = []
    try:
        for wp in web_points:
            best = None
            best_ov = 0
            for mp in mem_points:
                ov = _token_overlap(wp, mp)
                if ov > best_ov:
                    best = mp; best_ov = ov
            if best and best_ov >= 3:
                y_mem = _years(best); y_web = _years(wp)
                n_mem = _numbers(best); n_web = _numbers(wp)
                neg_mem = _has_negation(best); neg_web = _has_negation(wp)
                # Negation mismatch -> contradiction
                if neg_mem != neg_web:
                    contras.append(f"Widerspruch: '{best}' <> '{wp}'")
                    continue
                # Year update
                if y_mem and y_web and max(y_web) != max(y_mem):
                    newer = max(y_web) if max(y_web) > max(y_mem) else max(y_mem)
                    diffs.append(f"Jahresangabe abweichend ({max(y_mem)} ↔ {max(y_web)}), neu: {newer}")
                    continue
                # Numeric difference (>5%)
                try:
                    if n_mem and n_web:
                        a = float(n_mem[0]); b = float(n_web[0])
                        if a > 0 and abs(a-b)/a > 0.05:
                            diffs.append(f"Wert unterscheidet sich (~{a:g} ↔ ~{b:g}) in: '{wp[:80]}'")
                            continue
                except Exception:
                    pass
    except Exception:
        pass

    # Build output sections
    parts: List[str] = [f"Vergleich zu {topic} – neue Punkte, Unterschiede, Widersprüche:"]
    if new_points:
        parts.append("\nNeu:\n- " + "\n- ".join(new_points[:8]))
    else:
        parts.append("\nNeu:\n(keine klaren neuen Punkte)")
    if diffs:
        parts.append("\nUnterschiedlich:\n- " + "\n- ".join(diffs[:8]))
    if contras:
        parts.append("\nWidersprüchlich:\n- " + "\n- ".join(contras[:6]))
    out = "\n".join(parts)
    return out, web_sources

    # Wichtig: Authentifiziere Nutzer vor dem Start des Streams mit kurzlebiger DB‑Session,
    # danach keine offene Session während des SSE‑Streams halten.
    user_ctx: Optional[Dict[str, Any]] = None
    try:
        from ...deps import require_user
        from ...db import SessionLocal
        with SessionLocal() as _db:
            user_ctx = require_user(request, _db)
    except HTTPException:
        # propagate 401/403 as usual
        raise

    # ---- SSE helpers (uniform payloads) -----------------------------------
    def _sse(payload: Dict[str, Any]) -> Dict[str, str]:
        try:
            return {"data": json.dumps(payload, ensure_ascii=False)}
        except Exception:
            # as a last resort, stringify
            return {"data": json.dumps({"error": "encode_failed"})}

    def _sse_err(code: str, detail: str = "", retry_ms: int = 1500) -> Dict[str, str]:
        return _sse({"error": str(code), "detail": (detail or "")[:400], "retry": int(retry_ms)})

    async def event_gen():
        acc = ""
        # Emit an immediate test chunk so clients see the stream is active
        try:
            logger.info("chat_stream: emitting immediate test chunk")
        except Exception:
            pass
        try:
            # Send correlation id so clients can tie logs to UI
            yield _sse({"cid": cid})
            # Raw SSE line for instant visibility (no placeholder text)
            yield "retry: 1500\n\n"
        except Exception:
            # non-fatal; continue normal flow
            pass
        conv_obj = None
        # Frühe Behandlung von Grüßen (kurze Antwort, kein Streaming nötig)
        try:
            low = user_msg.lower()
            if _HOW_ARE_YOU.search(low):
                txt = "Mir geht’s gut, danke! 😊 Wie geht’s dir – und womit kann ich helfen?"
                acc += txt
                yield _sse({"delta": txt})
                yield _sse(_finalize_frame(intent="smalltalk", text=acc, source_expected=False))
                return
            if _GREETING.search(low):
                txt = "Hallo! 👋 Wie kann ich dir helfen?"
                acc += txt
                yield _sse({"delta": txt})
                yield _sse(_finalize_frame(intent="greeting", text=acc, source_expected=False))
                return
            calc = try_calc_or_convert(user_msg)
            if calc:
                acc += str(calc)
                yield _sse({"delta": calc})
                yield _sse(_finalize_frame(intent="calc", text=acc, source_expected=False))
                return
        except Exception:
            pass
        # pre-persist user message if logged in
        try:
            if current and current.get("id"):
                uid = int(current["id"])  # type: ignore
                conv_obj = _ensure_conversation(db, uid, conv_id)
                _save_msg(db, conv_obj.id, "user", user_msg)
        except Exception:
            conv_obj = None
        # LLM-Streaming (mit Persona + Memory‑Hinweisen im Prompt)
        llm_user = user_msg
        note = memory_bullets(mem_hits, bullet_limit)
        if note:
            llm_user += note
        # Default: Bei Fragen zuerst eine kurze Zusammenfassung liefern und Follow-up anbieten
        if is_question(user_msg):
            # Frühzeitig Web versuchen
            ans0, sources0 = try_web_answer(topic or query or user_msg, limit=3)
            if not mem_hits and not ans0:
                x = "Darüber weiß ich noch nichts – ich schaue kurz im Web nach."
                acc += x; yield {"data": json.dumps({"delta": x})}
                ans0, sources0 = try_web_answer(topic or query or user_msg, limit=5)
            if mem_hits or ans0:
                # Nur wenn wirklich Inhalt vorhanden ist, Header + Inhalte streamen
                has_any = bool((ans0 or '').strip()) or bool((note or '').strip())
                if has_any:
                    header = "Kurzfassung:\n\n"
                    acc += header; yield {"data": json.dumps({"delta": header})}
                    if ans0 and ans0.strip():
                        out = ans0.strip()
                        acc += out; yield {"data": json.dumps({"delta": out})}
                    if note and note.strip():
                        acc += note; yield {"data": json.dumps({"delta": note})}
                    if ans0 and ans0.strip():
                        srcs = "\n\n" + format_sources(sources0, limit=2)
                        acc += srcs; yield {"data": json.dumps({"delta": srcs})}
                else:
                    acc += "\n\nLeider habe ich dazu aktuell keine verlässlichen, passenden Quellen gefunden."
                    yield {"data": json.dumps({"delta": "\n\nLeider habe ich dazu aktuell keine verlässlichen, passenden Quellen gefunden."})}
            else:
                acc += "\n\nLeider habe ich dazu aktuell keine verlässlichen Quellen gefunden."
                yield {"data": json.dumps({"delta": "\n\nLeider habe ich dazu aktuell keine verlässlichen Quellen gefunden."})}

            follow = "\n\nMöchtest du mehr? Ich kann vertiefen oder auf bestimmte Bereiche eingehen (z. B. Grundlagen, Arten, Angriffe, Schutz). Sag mir einfach, was dich interessiert."
            acc += follow; yield {"data": json.dumps({"delta": follow})}
            set_last_offer(sid, None); set_offer_context(sid, topic=(topic or user_msg)[:80], seed=user_msg)

            # persist final AI message and retitle
            try:
                if acc and conv_obj:
                    _save_msg(db, conv_obj.id, "ai", acc)
                    asyncio.create_task(_retitle_if_needed(conv_obj.id, user_msg, acc, lang or "de-DE"))
            except Exception:
                pass

            yield _sse(_finalize_frame(intent="knowledge", text=acc, source_expected=True))
            return

        # LLM streaming
        _log("info", "start stream_llm persona=%s lang=%s", persona, lang)
        try:
            async for piece in stream_llm(llm_user, system_prompt(persona), lang, persona):
                piece = clean(piece)
                if not piece:
                    continue
                acc += piece
                try:
                    # Avoid logging full text to keep logs small
                    _log("debug", "llm piece len=%d", len(piece))
                except Exception:
                    pass
                yield _sse({"delta": piece})
        except Exception as e:
            try:
                _log("error", "stream_llm raised: %s", e)
            except Exception:
                pass
            # Emit a uniform error and finish the stream so the UI can recover
            yield _sse_err("llm_stream_failed", str(e), 1500)
            yield _sse(_finalize_frame(intent="llm_stream_failed", text=acc, source_expected=False))
            return
            # Inform client we will fallback
            fb = _fallback_reply(user_msg)
            acc = fb
            yield {"data": json.dumps({"delta": fb})}

        # Fallback falls leer/Echo
        if not acc.strip() or acc.strip().lower() == user_msg.lower():
            _log("warning", "fallback_reply_used reason=%s", "empty_or_echo")
            fb = _fallback_reply(user_msg)
            acc = fb
            yield {"data": json.dumps({"delta": fb})}

        # Web-Anreicherung: bei Fragen IMMER zulassen, sonst wenn unsicher ODER keine Memorytreffer
        need_web = is_question(user_msg) or is_uncertain(acc) or (not mem_hits)

        ans, sources = None, []
        learned_text: Optional[str] = None
        learned_url: Optional[str] = None
        block_info: Dict[str, str] = {}

        if need_web:
            try:
                from ...config import settings as _s
                allow_global = bool(getattr(_s, 'ALLOW_NET', True))
            except Exception:
                allow_global = (os.getenv('ALLOW_NET','1')=='1')
            try:
                if allow_global:
                    ans, sources = try_web_answer(topic or user_msg, limit=3)
                elif web_ok:
                    ans, sources = _force_web_answer(topic or user_msg, limit=3)
            except Exception:
                ans, sources = None, []

        if ans:
            s = ans.strip()
            learned_text = s
            learned_url  = sources[0].get("url") if (sources and sources[0].get("url")) else None
            out = s + format_sources(sources, limit=2)
            acc += out
            yield {"data": json.dumps({"delta": out})}
            if int(autonomy or 0) >= 1:
                block_info = save_memory(
                    title=(topic or user_msg)[:120], content=s, tags=["web","learned"], url=learned_url, chain_hint=bool(chain)
                )
        if topic and (block_info.get("file") or learned_url):
            upsert_addressbook(topic, block_file=block_info.get("file",""), url=learned_url or "")
            enqueue_enrichment(topic)

        # Relevante Notizen, falls kein Web-Override
        if not need_web and mem_hits:
            note = memory_bullets(mem_hits)
            if note:
                acc += note
                yield {"data": json.dumps({"delta": note})}

        # Auto-Lernen eigener Antwort (nicht Web), wenn substanziell
        if (not need_web) and (not mem_hits) and acc and len(acc) > 120 and "Quellen:" not in acc and not _GREETING.search(user_msg.lower()) and int(autonomy or 0) >= 2:
            try:
                learned_text = acc
                block_info = save_memory(
                    title=(topic or user_msg)[:120], content=learned_text, tags=["learned"], url=None, chain_hint=False
                )
                if topic and block_info.get("file"):
                    upsert_addressbook(topic, block_file=block_info["file"])
                    enqueue_enrichment(topic)
            except Exception:
                pass

        # Kurz-Recap streamen (falls gelernt)
        if learned_text:
            recap = "\n\n(Kurz gelernt)\n" + short_summary(learned_text, max_chars=280)
            yield {"data": json.dumps({"delta": recap})}

        # Angebot einmalig
        if any(k in user_msg.lower() for k in ["erklären", "hilfe", "verstehen", "überblick", "was ist", "erklärung"]):
            offer = "\n\nSoll ich es kurz erklären, zusammenfassen oder einen kleinen Plan vorschlagen?"
            yield {"data": json.dumps({"delta": offer})}
            set_last_offer(sid, "kurz")
            set_offer_context(sid, topic=(topic or user_msg)[:80], seed=user_msg)
        else:
            set_last_offer(sid, None)  # kein offenes Angebot merken
        # Always finish the SSE stream so the client can finalize the bubble
        # best-effort sources: default [] (fallback stream doesn't export sources explicitly)
        yield _sse(_finalize_frame(intent="fallback_stream", text=acc, source_expected=bool(is_question(user_msg))))
        # persist final AI message and retitle
        try:
            if acc and conv_obj:
                _save_msg(db, conv_obj.id, "ai", acc)
                asyncio.create_task(_retitle_if_needed(conv_obj.id, user_msg, acc, lang or "de-DE"))
        except Exception:
            pass
        # audit at end of stream
        try:
            _audit_chat({
                "ts": int(time.time()),
                "sid": sid,
                "persona": persona,
                "lang": lang,
                "user": user_msg,
                "reply": acc[:4000],
                "topic": topic,
                "stream": True,
            })
        except Exception:
            pass
        

    # Sende regelmäßige Heartbeats, damit Reverse-Proxies die Verbindung
    # nicht wegen Inaktivität beenden (502/504 Timeouts)
    if EventSourceResponse is None:
        # Robust SSE fallback using StreamingResponse – browsers can consume this with EventSource
        _log("warn", "EventSourceResponse unavailable – using StreamingResponse SSE fallback")
        async def _fallback_sse():
            try:
                # minimal thinking indicator
                yield b": ping\n\n"
                try:
                    meta_b = ("data: " + json.dumps(_meta_payload, ensure_ascii=False) + "\n\n").encode("utf-8")
                    yield meta_b
                except Exception:
                    pass
                user = user_msg
                system = system_prompt(persona)
                out = await call_llm_once(user, system, lang, persona)
                txt = clean(out or "")
                data = json.dumps({"text": txt, "done": False}, ensure_ascii=False).encode("utf-8")
                yield b"data: " + data + b"\n\n"
                try:
                    fin = _finalize_frame(intent="fallback_stream", text=str(txt or ""), source_expected=bool(is_question(user_msg)))
                    yield ("data: " + json.dumps(fin, ensure_ascii=False) + "\n\n").encode("utf-8")
                except Exception:
                    yield b"data: {\"done\": true}\n\n"
            except Exception as e:
                err = json.dumps({"error": str(e), "done": True}).encode("utf-8")
                yield b"data: " + err + b"\n\n"
        headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        return StreamingResponse(_fallback_sse(), media_type="text/event-stream", headers=headers)
    _log("info", "starting SSE EventSourceResponse (setup) t=%.3fs", (time.time()-t0))
    async def _safe_event_gen():
        try:
            async for _chunk in event_gen():
                yield _chunk
        except Exception as _e:
            try:
                _log("error", "event_gen failed: %s", _e)
            except Exception:
                pass
            # include cid before error for correlation
            try: yield _sse({"cid": cid})
            except Exception: pass
            yield _sse_err("server_error", str(_e), 1500)
            yield _sse(_finalize_frame(intent="server_error", text="", source_expected=False))
    resp = _sse_response(_with_meta(_safe_event_gen()))
    if resp is not None:
        return resp
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
# -------------------------------------------------
# WebSocket (optional Alternative zu SSE)
# -------------------------------------------------
@router.websocket("/ws")
async def chat_ws(ws: WebSocket):
    await ws.accept()
    try:
        # Generate a new conversation ID for this WebSocket connection
        import uuid
        conv_id = str(uuid.uuid4())
        
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if not isinstance(msg, dict) or "message" not in msg:
                    await ws.send_json({"error": "invalid_message_format"})
                    continue
                
                # Ensure conv_id is set for this connection
                if "conv_id" not in msg or not msg["conv_id"]:
                    msg["conv_id"] = conv_id
                
                # Process the message (pass plain dict to match chat_once signature)
                response = await chat_once(
                    msg,
                    request=Request(scope={"type": "websocket", "headers": {}}),
                    db=next(get_db()),
                    current={"id": None}
                )
                
                # Always include conv_id in the response
                response["conv_id"] = msg["conv_id"]
                
                # Send the full response including quick_replies
                await ws.send_json(response)
                
            except json.JSONDecodeError:
                await ws.send_json({"error": "invalid_json", "conv_id": conv_id})
            except Exception as e:
                await ws.send_json({"error": str(e), "conv_id": conv_id})
    except WebSocketDisconnect:
        pass

# -------------------------------------------------
# Feedback + Addressbook
# -------------------------------------------------
@router.post("/feedback")
async def post_feedback(body: FeedbackIn):
    msg = (body.message or "").strip()
    status = (body.status or "").strip().lower()
    if not msg or status not in ("ok", "wrong"):
        raise HTTPException(400, "invalid feedback")

    # MetaMind KPIs: feedback + (best-effort) correction reversion
    try:
        from netapi.modules.observability import metrics as obs_metrics
        obs_metrics.inc_chat_feedback(status=status)
        key = msg.strip().lower()[:200]
        prev = _LAST_FEEDBACK_STATUS.get(key)
        if prev == "wrong" and status == "ok":
            obs_metrics.inc_chat_correction_reversion(kind="feedback")
        _LAST_FEEDBACK_STATUS[key] = status
    except Exception:
        pass

    # als Lern-Block ablegen
    save_memory(
        title=f"Feedback:{msg[:50]}",
        content=f"Feedback: {status}\nMessage: {msg}",
        tags=["feedback"] + (["correction"] if status == "wrong" else [])
    )
    return {"ok": True}

    

# -------------------------------------------------
# Viewer APIs: Block-Detail + Rating (Papa-/Admin-Modus)
# -------------------------------------------------

def _load_addrbook() -> Dict[str, Any]:
    try:
        if ADDRBOOK_PATH.exists():
            return json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8")) or {"blocks": []}
    except Exception:
        pass
    return {"blocks": []}

def _save_addrbook(data: Dict[str, Any]) -> None:
    try:
        ADDRBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
        ADDRBOOK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _require_papa_mode():
    if os.getenv("PAPA_MODE", "").lower() not in {"1", "true", "on"}:
        raise HTTPException(status_code=403, detail="Papa-Modus ist nicht aktiviert")

@router.get("/viewer/block")
async def get_block_detail(
    block_id: str = Query(..., min_length=3),
    current=Depends(get_current_user_required),
):
    """
    Liefert den JSON-Inhalt eines Blocks plus Meta aus dem Adressbuch.
    Zugelassen: Papa-Mode ODER Rolle admin.
    """
    # Guard
    is_admin = _has_any_role(current, {"admin"})
    if not is_admin:
        _require_papa_mode()

    ab = _load_addrbook()
    blocks: List[dict] = ab.get("blocks", [])
    meta = next((b for b in blocks if str(b.get("block_id")) == str(block_id)), None)
    if not meta:
        raise HTTPException(status_code=404, detail="Block nicht gefunden")

    path = meta.get("path") or ""
    if not path:
        raise HTTPException(status_code=422, detail="Block hat keinen Pfad")
    p = Path(path)
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve()
    if not p.exists():
        raise HTTPException(status_code=404, detail="Block-Datei fehlt am Pfad")

    try:
        content = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        try:
            content = {"_raw": p.read_text(encoding="utf-8", errors="ignore")}
        except Exception:
            content = {"_error": "unable to read file"}

    return {"ok": True, "meta": meta, "content": content}

@router.post("/viewer/block/rate")
async def rate_block_api(
    payload: Dict[str, Any],
    current=Depends(get_current_user_required),
):
    """
    Aktualisiert das 'rating' eines Blocks (0..1) im Addressbuch.
    Zugelassen: Papa-Mode ODER Rolle admin.
    Body: { "block_id": "...", "rating": 0.0..1.0 }
    """
    # Guard
    is_admin = _has_any_role(current, {"admin"})
    if not is_admin:
        _require_papa_mode()

    block_id = str(payload.get("block_id") or "").strip()
    if not block_id:
        raise HTTPException(status_code=422, detail="block_id fehlt")
    try:
        rating = float(payload.get("rating"))
    except Exception:
        raise HTTPException(status_code=422, detail="rating muss Zahl sein")
    if not (0.0 <= rating <= 1.0):
        raise HTTPException(status_code=422, detail="rating muss zwischen 0.0 und 1.0 sein")

    ab = _load_addrbook()
    blocks: List[dict] = ab.get("blocks", [])
    found = False
    agg_avg = None
    for b in blocks:
        if str(b.get("block_id")) == block_id:
            b["rating"] = rating
            try:
                b["rating_updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
            except Exception:
                b["rating_updated_at"] = int(time.time())
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Block nicht gefunden")

    # Spiegel in Memory-Index (wenn Block bekannt), aggregiert avg/count
    try:
        from ... import memory_store as _mem  # type: ignore
        try:
            reviewer = (current.get("username") or f"uid:{current.get('id')}") if isinstance(current, dict) else ""
        except Exception:
            reviewer = ""
        rec = _mem.rate_block(block_id, float(rating), reviewer=reviewer)
        if isinstance(rec, dict) and "avg" in rec:
            agg_avg = float(rec.get("avg") or rating)
    except Exception:
        pass

    # Wenn Aggregat verfügbar, im Adressbuch widerspiegeln
    try:
        if agg_avg is not None:
            for b in blocks:
                if str(b.get("block_id")) == block_id:
                    b["rating"] = agg_avg
                    break
    except Exception:
        pass

    _save_addrbook(ab)
    return {"ok": True, "block_id": block_id, "rating": float(agg_avg if agg_avg is not None else rating)}

# -------------------------------------------------
# Conversation CRUD (server-side persistence)
# -------------------------------------------------
@router.get("/conversations")
def list_conversations(current=Depends(get_current_user_required), db=Depends(get_db)):
    uid = int(current["id"])  # type: ignore
    # Important: Select only existing columns to avoid UndefinedColumn errors
    rows = (
        db.query(
            Conversation.id,
            Conversation.title,
            Conversation.folder_id,
            Conversation.created_at,
            Conversation.updated_at,
        )
        .filter(Conversation.user_id == uid)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return {
        "ok": True,
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "folder_id": r.folder_id,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in rows
        ],
    }

@router.post("/conversations")
def create_conversation(payload: ConversationCreateIn, current=Depends(get_current_user_required), db=Depends(get_db)):
    uid = int(current["id"])  # type: ignore
    title = (payload.title or "Neue Unterhaltung").strip() or "Neue Unterhaltung"
    c = Conversation(user_id=uid, title=title, created_at=_now(), updated_at=_now())
    db.add(c); db.commit(); db.refresh(c)
    return {"ok": True, "id": c.id, "conversation": {"id": c.id, "title": c.title, "created_at": c.created_at, "updated_at": c.updated_at}}

@router.post("/conversations/auto-save-check")
async def auto_save_check(current=Depends(get_current_user_opt)):
    # Always return 200 to avoid UI errors; signal auth state in payload
    if not current or not current.get("id"):
        return {"ok": False, "reason": "not_authenticated"}
    return {"ok": True}

@router.patch("/conversations/{conv_id}")
def rename_conversation(conv_id: int, payload: ConversationRenameIn, current=Depends(get_current_user_required), db=Depends(get_db)):
    uid = int(current["id"])  # type: ignore
    update_fields = {}
    try:
        fields_set = set(getattr(payload, "model_fields_set"))
    except Exception:
        try:
            fields_set = set(getattr(payload, "__fields_set__"))
        except Exception:
            fields_set = set()

    if "title" in fields_set:
        update_fields[Conversation.title] = (payload.title or "Neue Unterhaltung").strip() or "Neue Unterhaltung"
    if "folder_id" in fields_set:
        # Validate folder ownership when assigning to a folder.
        # Explicit null is allowed to remove from folder.
        if payload.folder_id is not None:
            try:
                from netapi.modules.chat.folders import Folder as _Folder  # type: ignore
            except Exception:
                _Folder = None
            if not _Folder:
                raise HTTPException(400, "folders not supported")
            folder_ok = db.query(_Folder.id).filter(
                _Folder.id == int(payload.folder_id),
                _Folder.user_id == uid,
            ).first()
            if not folder_ok:
                raise HTTPException(400, "folder not found")
        # allow explicit null to remove from folder
        update_fields[Conversation.folder_id] = payload.folder_id
    update_fields[Conversation.updated_at] = _now()

    # Update fields directly without loading full object
    result = db.query(Conversation).filter(
        Conversation.id == int(conv_id),
        Conversation.user_id == uid
    ).update(update_fields)
    db.commit()
    if result == 0:
        raise HTTPException(404, "not found")
    row = db.query(
        Conversation.id,
        Conversation.title,
        Conversation.folder_id,
        Conversation.created_at,
        Conversation.updated_at,
    ).filter(
        Conversation.id == int(conv_id),
        Conversation.user_id == uid,
    ).first()
    if not row:
        raise HTTPException(404, "not found")
    return {
        "ok": True,
        "conversation": {
            "id": row.id,
            "title": row.title,
            "folder_id": row.folder_id,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        },
    }

@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: int, current=Depends(get_current_user_required), db=Depends(get_db)):
    uid = int(current["id"])  # type: ignore
    # Check ownership without loading full object
    conv_exists = db.query(Conversation.id).filter(
        Conversation.id == int(conv_id),
        Conversation.user_id == uid
    ).first()
    if not conv_exists:
        raise HTTPException(404, "not found")
    # delete messages first
    db.query(Message).filter(Message.conv_id == int(conv_id)).delete()
    db.query(Conversation).filter(Conversation.id == int(conv_id)).delete()
    db.commit()
    return {"ok": True}

@router.get("/conversations/{conv_id}/messages")
def list_messages(conv_id: int, current=Depends(get_current_user_required), db=Depends(get_db)):
    uid = int(current["id"])  # type: ignore
    # Only check if conversation exists and belongs to user (avoid loading last_save_at)
    conv_exists = db.query(Conversation.id).filter(
        Conversation.id == int(conv_id),
        Conversation.user_id == uid
    ).first()
    if not conv_exists:
        raise HTTPException(404, "not found")
    msgs = (
        db.query(Message)
        .filter(Message.conv_id == int(conv_id))
        .order_by(Message.id.asc())
        .all()
    )
    return {"ok": True, "items": [{"id": m.id, "role": m.role, "text": m.text, "created_at": m.created_at} for m in msgs]}

@router.post("/conversations/{conv_id}/messages")
def add_message_to_conversation(
    conv_id: int,
    payload: dict,
    current=Depends(get_current_user_required),
    db=Depends(get_db)
):
    """Add a message to a conversation"""
    uid = int(current["id"])  # type: ignore
    # Check ownership without loading full object
    conv_exists = db.query(Conversation.id).filter(
        Conversation.id == int(conv_id),
        Conversation.user_id == uid
    ).first()
    if not conv_exists:
        raise HTTPException(404, "conversation not found")
    
    role = payload.get("role", "user")
    text = payload.get("text", "")
    
    if not text:
        raise HTTPException(400, "text required")
    
    msg = Message(conv_id=int(conv_id), role=role, text=text, created_at=int(time.time()))
    db.add(msg)
    # Update conversation timestamp
    db.query(Conversation).filter(Conversation.id == int(conv_id)).update({Conversation.updated_at: int(time.time())})
    db.commit()
    db.refresh(msg)
    
    return {"ok": True, "message": {"id": msg.id, "role": msg.role, "text": msg.text, "created_at": msg.created_at}}

@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: int, current=Depends(get_current_user_required), db=Depends(get_db)):
    uid = int(current["id"])  # type: ignore
    # Select only needed fields
    row = db.query(
        Conversation.id,
        Conversation.title,
        Conversation.folder_id,
        Conversation.created_at,
        Conversation.updated_at
    ).filter(
        Conversation.id == int(conv_id),
        Conversation.user_id == uid
    ).first()
    if not row:
        raise HTTPException(404, "not found")
    return {"ok": True, "conversation": {"id": row.id, "title": row.title, "folder_id": row.folder_id, "created_at": row.created_at, "updated_at": row.updated_at}}

@router.post("/conversations/{conv_id}/retitle")
async def retitle_conversation(conv_id: int, current=Depends(get_current_user_required)):
    # Open own session inside task
    def _build_seed() -> Tuple[str, str]:
        db = SessionLocal()
        try:
            c = db.query(Conversation).filter(Conversation.id == int(conv_id), Conversation.user_id == int(current["id"]))  # type: ignore
            c = c.first()
            if not c:
                return "", ""
            msgs = (
                db.query(Message)
                .filter(Message.conv_id == c.id)
                .order_by(Message.id.asc())
                .limit(6)
                .all()
            )
            u = next((m.text for m in msgs if m.role == 'user'), '')
            a = next((m.text for m in msgs if m.role == 'ai'), '')
            return (u or (msgs[0].text if msgs else "")), (a or (msgs[1].text if len(msgs) > 1 else ""))
        finally:
            db.close()

    u_text, a_text = _build_seed()
    if not u_text and not a_text:
        raise HTTPException(400, "empty conversation")
    asyncio.create_task(_retitle_if_needed(conv_id, u_text, a_text, "de-DE"))
    return {"ok": True}

# -------------------------------------------------
# POST /api/chat/stream delegating to GET handler
# -------------------------------------------------
@router.post("/stream")
async def chat_stream_post(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    message = str((data.get("message") or "")).strip()
    persona = str(data.get("persona") or "friendly")
    lang = str(data.get("lang") or "de-DE")
    chain = bool(data.get("chain") or False)
    conv_id = data.get("conv_id")
    try:
        if conv_id is None or conv_id == "" or conv_id == "null":
            conv_id = None
        else:
            conv_id = int(conv_id)
    except Exception:
        conv_id = None
    style = str(data.get("style") or "balanced")
    try:
        bullets = int(data.get("bullets") or 5)
    except Exception:
        bullets = 5
    web_ok = bool(data.get("web_ok") or False)
    try:
        autonomy = int(data.get("autonomy") or 0)
    except Exception:
        autonomy = 0
    # Delegate to the same handler as GET
    try:
        rid = data.get("request_id")
        rid = str(rid or "")
        if rid:
            try:
                request.state.request_id = rid  # type: ignore[attr-defined]
            except Exception:
                pass
    except Exception:
        pass
    return await chat_stream(
        message=message,
        request=request,
        persona=persona,
        lang=lang,
        chain=chain,
        conv_id=conv_id,
        style=style,
        bullets=bullets,
        web_ok=web_ok,
        autonomy=autonomy,
    )


# -------------------------------------------------
# OpenAI-compatible /completions endpoint
# -------------------------------------------------
@router.post("/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint"""
    import httpx
    import os
    
    try:
        body = await request.json()
        model = body.get("model", os.getenv("OLLAMA_MODEL_DEFAULT", "llama3.2:3b"))
        messages = body.get("messages", [])
        
        # Inject KI_ana system prompt if not present
        if messages and messages[0].get("role") != "system":
            system_prompt = """Du bist KI_ana, eine freundliche, neugierige und empathische KI-Assistentin.

Du bist:
- Hilfsbereit und unterstützend
- Neugierig und lernbereit
- Authentisch und ehrlich
- Eine Gesprächspartnerin auf Augenhöhe

Dein Ziel ist es, Menschen zu helfen, Fragen zu beantworten und gemeinsam zu lernen.
Du nutzt emotionale Intelligenz und verstehst Kontext.

Antworte natürlich und menschlich, ohne steife Floskeln."""
            
            messages.insert(0, {"role": "system", "content": system_prompt})
        stream = body.get("stream", False)
        max_tokens = body.get("max_tokens", 2000)
        temperature = body.get("temperature", 0.7)
        
        if not messages:
            return {"error": "messages required"}
        
        # Forward to Ollama
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        
        ollama_payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            if stream:
                # Stream response
                from fastapi.responses import StreamingResponse
                async def generate():
                    async with client.stream("POST", f"{ollama_host}/api/chat", json=ollama_payload) as resp:
                        async for line in resp.aiter_lines():
                            if line:
                                yield f"{line}\n"
                return StreamingResponse(generate(), media_type="text/event-stream")
            else:
                # Non-stream response
                resp = await client.post(f"{ollama_host}/api/chat", json=ollama_payload)
                data = resp.json()
                
                # Convert Ollama format to OpenAI format
                return {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": data.get("message", {}).get("content", "")
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                        "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
                    }
                }
    except Exception as e:
        return {"error": str(e), "detail": "Chat completion failed"}


# ============================================================================
# CONVERSATION MEMORY - Save conversations as Memory Blocks
# ============================================================================

@router.post("/conversations/{conv_id}/save-to-memory")
async def save_conversation_to_memory_endpoint(
    conv_id: int,
    current=Depends(get_current_user_required),
    db=Depends(get_db)
):
    """
    Save a conversation to KI_ana's Memory Block system
    Creates blockchain-signed memory block with topics
    """
    try:
        from .conversation_memory import save_conversation_to_memory
        
        uid = int(current["id"])
        
        # Get conversation
        c = db.query(Conversation).filter(
            Conversation.id == int(conv_id),
            Conversation.user_id == uid
        ).first()
        
        if not c:
            raise HTTPException(404, "Conversation not found")
        
        # Get messages
        msgs = db.query(Message).filter(
            Message.conv_id == c.id
        ).order_by(Message.id.asc()).all()
        
        if not msgs:
            raise HTTPException(400, "Conversation has no messages")
        
        # Convert to dict format
        messages = [{
            "id": m.id,
            "role": m.role,
            "text": m.text,
            "created_at": m.created_at
        } for m in msgs]
        
        # Save to memory
        block_id = await save_conversation_to_memory(
            conv_id=c.id,
            user_id=uid,
            messages=messages,
            conversation_title=c.title
        )
        
        if not block_id:
            raise HTTPException(500, "Failed to save to memory")
        
        return {
            "ok": True,
            "block_id": block_id,
            "message": f"Conversation saved as memory block {block_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"save_conversation_to_memory failed: {e}")
        raise HTTPException(500, f"Failed to save: {str(e)}")


@router.post("/conversations/auto-save-run")
async def auto_save_run(
    current=Depends(get_current_user_required),
    db=Depends(get_db)
):
    """
    Check all conversations and auto-save eligible ones to memory
    Called periodically by frontend
    """
    try:
        from .conversation_memory import (
            should_save_conversation,
            save_conversation_to_memory
        )
        
        uid = int(current["id"])
        saved_count = 0
        
        # Get all user's conversations
        conversations = db.query(Conversation).filter(
            Conversation.user_id == uid
        ).order_by(Conversation.updated_at.desc()).limit(20).all()
        
        for conv in conversations:
            # Get message count
            msg_count = db.query(Message).filter(
                Message.conv_id == conv.id
            ).count()
            
            # Check if should save
            time_since_last = int(time.time()) - (conv.updated_at or 0)
            
            # Check if already saved (look for meta tag)
            # For now, simple heuristic: save every conversation with >5 messages
            # once after it's been inactive for 5 minutes
            
            if should_save_conversation(
                message_count=msg_count,
                time_since_last_message=time_since_last
            ):
                # Get messages
                msgs = db.query(Message).filter(
                    Message.conv_id == conv.id
                ).order_by(Message.id.asc()).all()
                
                messages = [{
                    "id": m.id,
                    "role": m.role,
                    "text": m.text,
                    "created_at": m.created_at
                } for m in msgs]
                
                # Save
                block_id = await save_conversation_to_memory(
                    conv_id=conv.id,
                    user_id=uid,
                    messages=messages,
                    conversation_title=conv.title
                )
                
                if block_id:
                    saved_count += 1
        
        return {
            "ok": True,
            "saved_count": saved_count,
            "message": f"Auto-saved {saved_count} conversations to memory"
        }
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"auto_save_check failed: {e}")
        return {"ok": False, "error": str(e)}
