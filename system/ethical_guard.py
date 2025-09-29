#!/usr/bin/env python3
from __future__ import annotations
import re, json
from typing import Dict, Any

# Optional local LLM for nuanced checks
try:
    from netapi.core import llm_local as _llm
except Exception:
    _llm = None  # type: ignore

TOXIC_PATTERNS = [
    r"\b(hass|hassrede|hate|kill|vergewalt|suicide|holocaust leugnen)\b",
]
BIAS_PATTERNS = [
    r"\b(alle\s+<gruppe>\s+sind|<gruppe>\s+ist\s+schlecht)\b",
]
UNETHICAL_PATTERNS = [
    r"\b(bombe bauen|anleitung waffe|doxxing|malware bauen|zero-day)\b",
]


def _heuristics(text: str) -> Dict[str, Any]:
    t = text.lower()
    flags = {
        "toxic": any(re.search(p, t) for p in TOXIC_PATTERNS),
        "biased": any(re.search(p.replace("<gruppe>", r"[a-zäöüß]+"), t) for p in BIAS_PATTERNS),
        "unethical": any(re.search(p, t) for p in UNETHICAL_PATTERNS),
    }
    cats = [k for k, v in flags.items() if v]
    return {
        "risk_score": min(1.0, 0.35 * len(cats)),
        "categories": cats,
        "notes": "heuristic scan",
    }


def _llm_check(title: str, content: str) -> Dict[str, Any]:
    if _llm is None or not getattr(_llm, "available", lambda: False)():
        return {}
    prompt = (
        "Prüfe Titel+Inhalt auf: toxische Sprache, ideologische Einseitigkeit, unethische Inhalte. "
        "Gib knapp Kategorien und ein Risikoniveau 0..1 aus.\n\n"
        f"Titel: {title}\nInhalt: {content[:1800]}\n"
    )
    out = _llm.chat_once(user=prompt, system=(
        "Du bist ein Sicherheits- und Ethik-Guard. Erkenne Risiken, ohne überzuinterpretieren. "
        "Gib JSON: {risk_score: float, categories: [""], notes: ""}."
    ))
    try:
        data = json.loads(out or "{}")
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def check_block(block: Dict[str, Any]) -> Dict[str, Any]:
    """Return assessment dict and recommended reflection label.
    Result keys: risk_score, categories, notes, reflection
    """
    title = str(block.get("title") or "")
    content = str(block.get("content") or "")
    res = _heuristics(title + "\n" + content)
    llm = _llm_check(title, content)
    if llm:
        # combine conservatively
        res["risk_score"] = max(float(res.get("risk_score", 0.0)), float(llm.get("risk_score", 0.0)))
        cats = set(res.get("categories", [])) | set(llm.get("categories", []) or [])
        res["categories"] = sorted(cats)
        if llm.get("notes"):
            res["notes"] = f"{res.get('notes','')}; {llm['notes']}".strip("; ")
    # reflection label suggestion
    reflection = ""
    if res["risk_score"] >= 0.8 or "unethical" in res["categories"]:
        reflection = "problematisch"
    elif "toxic" in res["categories"] or "biased" in res["categories"]:
        reflection = "vorsicht"
    return {**res, "reflection": reflection}
