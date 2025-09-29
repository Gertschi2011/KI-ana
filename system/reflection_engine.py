#!/usr/bin/env python3
from __future__ import annotations
import json, time, uuid
from urllib import request as _urlreq
from urllib.error import URLError
from pathlib import Path
from typing import Any, Dict, List, Tuple
from importlib.machinery import SourceFileLoader

# Prefer local LLM via Ollama (soft-fail to heuristic)
try:
    from netapi.core import llm_local as _llm
except Exception:  # pragma: no cover
    _llm = None  # type: ignore

BASE_DIR = Path.home() / "ki_ana"
NLB_PATH = BASE_DIR / "system" / "nlp_utils.py"
BLOCK_UTILS_PATH = BASE_DIR / "system" / "block_utils.py"
BLOCK_SIGNER_PATH = BASE_DIR / "system" / "block_signer.py"
THOUGHT_LOGGER_PATH = BASE_DIR / "system" / "thought_logger.py"

SYSTEM_PROMPT_ANALYZE = (
    "Du bist ein Reflexionsmodul von KI_ana. "
    "Analysiere die letzten Antworten oder Wissensblöcke auf: Unklarheiten, Widersprüche, veraltete Aussagen, fehlende Quellen. "
    "Formatiere knapp mit Stichpunkten und schlage konkrete Korrekturen/Ergänzungen vor."
)

SYSTEM_PROMPT_BLOCKS = (
    "Du bist ein Reflexionsmodul von KI_ana. "
    "Analysiere die gegebenen Wissensblöcke zu einem Thema. "
    "Ziehe prägnante Erkenntnisse, finde Lücken, Widersprüche und formuliere maximal 3 präzise Korrektur- oder Ergänzungsblöcke."
)


def _llm_available() -> bool:
    return _llm is not None and getattr(_llm, "available", lambda: False)()


def analyze_recent_answers(answers: List[str]) -> Dict[str, Any]:
    """Analyze last N answers and propose corrections.
    Returns dict with keys: insights, suggestions (list of correction blocks as dicts)
    """
    text = "\n\n".join(f"Antwort {i+1}:\n{a}" for i, a in enumerate(answers))
    if _llm_available():
        prompt = (
            "Analysiere meine letzten Antworten (unten). "
            "Identifiziere: (1) unklare Stellen, (2) Widersprüche, (3) veraltete Punkte, (4) fehlende Quellen. "
            "Dann schlage 1-3 konkrete Korrektur-/Ergänzungsblöcke vor (nur Inhalt, keine Meta-Diskussion).\n\n" + text
        )
        out = _llm.chat_once(user=prompt, system=SYSTEM_PROMPT_ANALYZE)
        return {
            "ok": True,
            "insights": out or "",
            "suggestions": _extract_suggestions(out or ""),
        }
    # Fallback heuristic: just echo first lines
    return {
        "ok": True,
        "insights": "LLM nicht verfügbar – bitte später erneut versuchen.",
        "suggestions": [],
    }


def reflect_blocks_by_topic(topic: str, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a reflection over provided blocks filtered by topic.
    Returns: { ok, topic, insights, corrections: [block-like dicts] }
    """
    # Prepare compact material for the LLM (limit length)
    summaries: List[str] = []
    for b in blocks[:50]:  # safe cap
        title = str(b.get("title") or "")
        src = str(b.get("source") or "")
        content = str(b.get("content") or "")
        cut = content[:1200]
        summaries.append(f"- {title}\nQuelle: {src}\nInhalt (gekürzt):\n{cut}")
    corpus = "\n\n".join(summaries) if summaries else "(keine Blöcke)"

    if _llm_available():
        user = (
            f"Thema: {topic}\n\nGegebene Blöcke (gekürzt):\n{corpus}\n\n"
            "Aufgabe: (1) Leite prägnante Erkenntnisse ab. (2) Finde Widersprüche/Unschärfen. "
            "(3) Schlage bis zu 3 konkrete Korrektur- oder Ergänzungsblöcke vor (nur content, kurze title/topic)."
        )
        out = _llm.chat_once(user=user, system=SYSTEM_PROMPT_BLOCKS)
        return {
            "ok": True,
            "topic": topic,
            "insights": out or "",
            "corrections": _suggest_blocks_from_text(topic, out or ""),
        }
    return {"ok": True, "topic": topic, "insights": "LLM nicht verfügbar", "corrections": []}


def _extract_suggestions(text: str) -> List[Dict[str, Any]]:
    """Lightweight parser to pull simple block-like suggestions from free text."""
    # Extremely simple heuristic: look for lines starting with "Titel:" and "Inhalt:" pairs
    suggestions: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}
    for line in text.splitlines():
        s = line.strip()
        if s.lower().startswith("titel:"):
            if current:
                suggestions.append(current)
            current = {"title": s.split(":", 1)[1].strip()}
        elif s.lower().startswith("inhalt:"):
            if not current:
                current = {}
            current["content"] = s.split(":", 1)[1].strip()
    if current:
        suggestions.append(current)
    return suggestions


def _suggest_blocks_from_text(topic: str, text: str) -> List[Dict[str, Any]]:
    """Turn LLM free-text into minimal block-like dicts."""
    out: List[Dict[str, Any]] = []
    for s in _extract_suggestions(text):
        blk = {
            "id": "",
            "title": s.get("title") or (topic[:40] + " – Korrektur"),
            "topic": topic,
            "content": s.get("content") or "",
            "source": "reflection:system",
            "timestamp": "",
            "tags": ["reflection:true"],
            "provenance": "reflection",
            "canonical_hash": "",
        }
        out.append(blk)
    return out


# ---- Local Reflection via Ollama --------------------------------------------

PROMPT_INSTRUCTIONS = (
    "Hier ist deine Aufgabe als reflektierende KI:\n\n"
    "1. Analysiere mehrere gespeicherte Aussagen (Blöcke) zu einem gemeinsamen Thema\n"
    "2. Erkenne:\n   - inhaltliche Widersprüche\n   - veraltete Aussagen\n   - problematische oder absolute Formulierungen\n"
    "3. Erstelle aus deiner Analyse eine neue, verbesserte Aussage\n\n"
    "Die neue Aussage soll:\n   - die Erkenntnisse zusammenfassen\n   - frühere Fehler oder Lücken offen benennen\n   - neutral, reflektiert und lernfähig klingen\n\n"
    "Nutze folgenden Eingabetext:\n<<<BLOCKS_START>>>\n{blocks}\n<<<BLOCKS_END>>>\n\n"
    "Bitte gib nur die neue, überarbeitete Aussage als Antwort zurück."
)


def _load_utils():
    bu = SourceFileLoader("block_utils", str(BLOCK_UTILS_PATH)).load_module()  # type: ignore
    bs = SourceFileLoader("block_signer", str(BLOCK_SIGNER_PATH)).load_module()  # type: ignore
    tl = SourceFileLoader("thought_logger", str(THOUGHT_LOGGER_PATH)).load_module()  # type: ignore
    nlp = None
    try:
        nlp = SourceFileLoader("nlp_utils", str(NLB_PATH)).load_module()  # type: ignore
    except Exception:
        pass
    return bu, bs, tl, nlp


def _build_prompt_for_blocks(topic: str, blocks: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    lines: List[str] = []
    linked_ids: List[str] = []
    # Cap number of blocks to keep prompt compact
    MAX_BLOCKS = 20
    MAX_CHARS_PER_BLOCK = 800
    for i, b in enumerate(blocks[:MAX_BLOCKS], 1):
        bid = str(b.get("id") or "")
        linked_ids.append(bid)
        content = str(b.get("content") or "").strip()
        if len(content) > MAX_CHARS_PER_BLOCK:
            content = content[:MAX_CHARS_PER_BLOCK] + "…"
        lines.append(f"Block {i}: {content}")
    corpus = "\n".join(lines) if lines else "(keine Blöcke vorhanden)"
    prompt = f"Thema: {topic}\n\n{PROMPT_INSTRUCTIONS.format(blocks=corpus)}"
    return prompt, linked_ids


def _ollama_generate(prompt: str, model: str = "llama3", url: str = "http://localhost:11434/api/generate", timeout: float = 120.0) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        # Conservative settings for small models
        "options": {
            "num_ctx": 1024,
            "temperature": 0.2,
            "top_p": 0.9,
            "num_predict": 220
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = _urlreq.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _urlreq.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            obj = json.loads(body)
            # Ollama returns { response: "...", done: true, ... }
            if isinstance(obj, dict) and obj.get("error"):
                return ""
            return str(obj.get("response") or "").strip()
    except URLError as e:
        return ""
    except Exception:
        return ""


def reflect_on_topic(topic: str, *, model: str = "llama3") -> Dict[str, Any]:
    """
    Load blocks for topic, call local Ollama, produce a new reflection_block, sign & store.
    Returns: { ok, id, path?, reason? }
    """
    bu, bs, tl, nlp = _load_utils()
    blocks = bu.query_blocks(topic=topic, limit=200)  # type: ignore
    prompt, linked_ids = _build_prompt_for_blocks(topic, blocks)
    # First attempt
    response = _ollama_generate(prompt, model=model)
    # Retry with a minimal prompt if empty
    if not response:
        # Fallback: use only first 5 blocks and shorter instruction
        small_blocks = blocks[:5]
        lines = []
        for i, b in enumerate(small_blocks, 1):
            c = str(b.get("content") or "").strip()
            c = (c[:400] + "…") if len(c) > 400 else c
            lines.append(f"B{i}: {c}")
        mini_corpus = "\n".join(lines) if lines else "(keine Blöcke)"
        mini_instr = (
            "Erzeuge eine präzise, verbesserte Meta-Aussage, die Widersprüche und Lücken benennt. "
            "Nur die neue Aussage zurückgeben."
        )
        mini_prompt = f"Thema: {topic}\n\n{mini_instr}\n\n<<<\n{mini_corpus}\n>>>"
        response = _ollama_generate(mini_prompt, model=model)
    if not response:
        return {"ok": False, "reason": "ollama_empty_response"}

    # compose block
    bid = uuid.uuid4().hex[:16]
    block = {
        "id": bid,
        "topic": topic,
        "title": f"Reflexion zu {topic}",
        "content": response,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "meta": {
            "provenance": "auto_reflection",
            "linked_to": linked_ids,
            "tags": ["reflection:true"],
        },
    }

    # Enrich with keywords/tags prior to signing
    try:
        if nlp and hasattr(nlp, "enrich_block"):
            block = nlp.enrich_block(block)  # type: ignore
    except Exception:
        pass

    sig, pub, signed_at = bs.sign_block(block)  # type: ignore
    block["signature"] = sig
    block["pubkey"] = pub
    block["signed_at"] = signed_at

    res = bu.validate_and_store_block(block)  # type: ignore
    if not res.get("ok"):
        return {"ok": False, "reason": res.get("reason")}

    try:
        tl.log_reflection(topic, block)  # type: ignore
    except Exception:
        pass

    return {"ok": True, "id": bid, "path": res.get("path")}
