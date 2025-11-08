from __future__ import annotations
from typing import Any, Dict
import os
import logging
import httpx
from typing import Dict, Any
import json
import re
import inspect
import asyncio
import anyio

# Soft import of planner
try:
    from netapi.agent.planner import deliberate_pipeline  # type: ignore
except Exception:
    deliberate_pipeline = None  # type: ignore

logger = logging.getLogger(__name__)

def _build_ollama_url() -> str:
    """
    Baue eine gültige Basis-URL für Ollama:
    - bevorzugt OLLAMA_BASE_URL (mit oder ohne http://)
    - sonst OLLAMA_HOST(+PORT)
    - sonst localhost:11434
    """
    base = os.getenv("OLLAMA_BASE_URL")
    host = os.getenv("OLLAMA_HOST")
    port = os.getenv("OLLAMA_PORT", "11434")

    if base:
        base = base.strip()
        if not base.startswith("http://") and not base.startswith("https://"):
            base = f"http://{base}"
        return base.rstrip("/")

    if host:
        host = host.strip()
        if host.startswith("http://") or host.startswith("https://"):
            return host.rstrip("/")
        if ":" in host:
            return f"http://{host}".rstrip("/")
        return f"http://{host}:{port}".rstrip("/")

    return "http://localhost:11434"

OLLAMA_URL = _build_ollama_url()
OLLAMA_MODEL = (os.getenv("OLLAMA_MODEL") or os.getenv("OLLAMA_MODEL_DEFAULT") or "llama3.1")

async def call_llm(prompt: str) -> str:
    """Direct Ollama generate call. Returns plain text or empty string on error, logs verbosely."""
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    try:
        logger.info(
            "LLM: calling Ollama url=%s model=%s payload_prompt_len=%d",
            OLLAMA_URL, OLLAMA_MODEL, len(prompt or ""),
        )
    except Exception:
        pass
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
        try:
            logger.info("LLM: response status=%s body=%s", getattr(r, "status_code", None), (getattr(r, "text", "") or "")[:500])
        except Exception:
            pass
        r.raise_for_status()
        raw = r.text or ""
        text = ""
        try:
            data = json.loads(raw)
            text = (data.get("response") or data.get("text") or "").strip()
        except Exception as e_json:
            # Some Ollama builds may return JSONL chunks even when stream=False.
            # Fallback: parse line-by-line and concatenate 'response' fields.
            try:
                parts: list[str] = []
                for line in raw.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        seg = (obj.get("response") or obj.get("text") or "")
                        if seg:
                            parts.append(str(seg))
                    except Exception:
                        continue
                text = ("".join(parts)).strip()
                logger.info("LLM: used JSONL fallback, parts=%d final_len=%d", len(parts), len(text))
            except Exception:
                logger.warning("LLM: failed to parse response as JSON and JSONL: %s", e_json)
                text = ""
        if not text:
            try:
                logger.warning("LLM: empty response text from Ollama")
            except Exception:
                pass
        else:
            try:
                logger.info("LLM: final text length=%d", len(text))
            except Exception:
                pass
        return text
    except Exception as e:
        try:
            logger.error("LLM: error talking to Ollama: %s", e, exc_info=True)
        except Exception:
            pass
        return ""

async def reason_about(user_msg: str, *, persona: str, lang: str, style: str, bullets: int, logic: str, fmt: str,
                       retrieval_snippet: str = "", retrieval_ids: list[str] | None = None) -> Dict[str, Any]:
    """
    Thin wrapper around deliberate_pipeline returning a structured object.
    Note: The base planner signature currently does not accept retrieval_* kwargs.
    """
    if deliberate_pipeline is None:
        return {"analysis": "", "plan": "", "answer_candidate": "", "sources": [], "critic": ""}
    # Call with supported parameters only; handle both sync and async implementations.
    try:
        logger.info("LLM: sending prompt to Ollama...", extra={"len_user_msg": len(user_msg or ""), "persona": persona, "lang": lang, "style": style})
    except Exception:
        pass
    try:
        # Some builds ship an async deliberate_pipeline; support both
        if inspect.iscoroutinefunction(deliberate_pipeline):
            ans, srcs, plan_b, critic_b = await deliberate_pipeline(
                user_msg,
                persona=persona, lang=lang, style=style, bullets=bullets, logic=logic, fmt=fmt,
            )
        else:
            ans, srcs, plan_b, critic_b = await anyio.to_thread.run_sync(
                deliberate_pipeline,
                user_msg,
                persona=persona, lang=lang, style=style, bullets=bullets, logic=logic, fmt=fmt,
            )
        try:
            _prev = (ans or "").strip().replace("\n", " ")[:200]
            logger.info("LLM: got response from Ollama: %r", _prev)
        except Exception:
            pass
    except Exception as e:
        try:
            logger.error("LLM: error talking to Ollama: %s", e, exc_info=True)
        except Exception:
            pass
        # Graceful fallback: return empty answer with error marker
        return {
            "analysis": "",
            "plan": "",
            "answer_candidate": "",
            "sources": [],
            "critic": "",
            "error": str(e),
        }
    out: Dict[str, Any] = {
        "analysis": plan_b or "",
        "plan": plan_b or "",
        "answer_candidate": ans or "",
        "sources": srcs or [],
        "critic": critic_b or "",
    }
    return out


def is_low_confidence_answer(text: str) -> bool:
    if not text or not str(text).strip():
        return True
    t = str(text).lower()
    patterns = [
        r"ich bin mir nicht sicher",
        r"leider habe ich dazu keine informationen",
        r"ich habe dazu gerade keine klare antwort",
        r"darüber weiß ich noch nichts",
        r"es scheint",
        r"möglicherweise",
    ]
    try:
        for p in patterns:
            if re.search(p, t):
                return True
    except Exception:
        pass
    if len(str(text).strip()) < 10:
        return True
    return False
