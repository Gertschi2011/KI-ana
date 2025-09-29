from __future__ import annotations
"""
Lightweight adapter for a local LLM via Ollama HTTP API.
Environment:
  OLLAMA_HOST  default: http://127.0.0.1:11434
  OLLAMA_MODEL default: llama3.1:8b

Provides simple non-streaming and streaming helpers. All functions
soft‑fail and return None if unreachable so callers can fall back.
"""
import os
import json
from typing import Dict, Iterator, Optional

import requests

# Prefer app settings (from .env) and fall back to process env
try:
    from netapi.config import settings  # type: ignore
except Exception:  # pragma: no cover
    settings = None  # type: ignore

def _cfg(name: str, default: str) -> str:
    if settings is not None and hasattr(settings, name):
        try:
            v = getattr(settings, name)
            if isinstance(v, str) and v.strip():
                return v
        except Exception:
            pass
    return os.getenv(name, default)

OLLAMA_HOST = _cfg("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")

# Resolve model using DEFAULT/ALT pair with KIANA_MODEL_ID, while supporting legacy OLLAMA_MODEL
def _resolve_model() -> str:
    # Legacy explicit override wins if present
    legacy = (_cfg("OLLAMA_MODEL", "") or "").strip()
    if legacy:
        return legacy

    # Preferred: DEFAULT/ALT controlled by KIANA_MODEL_ID
    m_def = (_cfg("OLLAMA_MODEL_DEFAULT", "llama3.1:8b") or "llama3.1:8b").strip()
    m_alt = (_cfg("OLLAMA_MODEL_ALT", "") or "").strip()
    sel = (_cfg("KIANA_MODEL_ID", "") or "").strip()
    if sel and m_alt and sel == m_alt:
        return m_alt
    if sel and sel == m_def:
        return m_def
    # If no KIANA_MODEL_ID match, prefer DEFAULT; fall back to ALT if DEFAULT missing
    return m_def or m_alt or "llama3.1:8b"

OLLAMA_MODEL = _resolve_model()
DEFAULT_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "30"))


def available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        return r.ok
    except Exception:
        return False


def _messages(system: str, user: str) -> list[dict]:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": str(system)})
    msgs.append({"role": "user", "content": str(user)})
    return msgs


def chat_once(user: str, system: str = "", *, model: Optional[str] = None, json_response: bool = False) -> Optional[str]:
    """Calls Ollama /api/chat once and returns the assistant text or None on failure."""
    try:
        payload: Dict = {
            # Enforce locked single model from env; ignore provided model arg
            "model": OLLAMA_MODEL,
            "messages": _messages(system, user),
            "stream": False,
        }
        if json_response:
            payload["format"] = "json"
        r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=DEFAULT_TIMEOUT)
        if not r.ok:
            return None
        data = r.json()
        msg = (data or {}).get("message") or {}
        content = (msg or {}).get("content")
        return str(content) if content else None
    except Exception:
        return None


def chat_stream(user: str, system: str = "", *, model: Optional[str] = None) -> Iterator[str]:
    """Yields incremental chunks from Ollama stream. Falls back to no output on failure."""
    try:
        payload = {
            # Enforce locked single model from env; ignore provided model arg
            "model": OLLAMA_MODEL,
            "messages": _messages(system, user),
            "stream": True,
        }
        with requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=DEFAULT_TIMEOUT, stream=True) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("done"):
                        break
                    msg = (obj.get("message") or {}).get("content")
                    if msg:
                        yield str(msg)
                except Exception:
                    # ignore parse errors, keep stream going
                    continue
    except Exception:
        return
