#!/usr/bin/env python3
from __future__ import annotations
import json, time
from typing import Any, Dict, List, Optional
from pathlib import Path

BASE_DIR = Path.home() / "ki_ana"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"

# Optional LLM
try:
    from netapi.core import llm_local as _llm
except Exception:
    _llm = None  # type: ignore

try:
    from system.thought_logger import log_decision  # type: ignore
except Exception:
    def log_decision(**kwargs):
        pass

SCHEMA_HINT = (
    "Bewerte jeden Block nach: Klarheit, Hilfsbereitschaft, Faktentreue (0..1). "
    "Gib JSON-Liste: [{id, clarity, helpfulness, factuality, notes}]."
)


def _score_with_llm(blocks: List[Dict[str, Any]], topic: Optional[str]) -> List[Dict[str, Any]]:
    if not (_llm and getattr(_llm, "available", lambda: False)()):
        return []
    # Build compact context
    items = []
    for b in blocks[:20]:
        items.append({
            "id": b.get("id"),
            "title": b.get("title"),
            "topic": b.get("topic") or topic,
            "content": (b.get("content") or "")[:1000],
        })
    user = (
        (f"Thema: {topic}\n" if topic else "") +
        "Bewerte folgende Wissensauszüge:\n" + json.dumps(items, ensure_ascii=False)
    )
    out = _llm.chat_once(user=user, system=(
        "Du bist Evaluator für KI_ana. "
        "Beurteile Klarheit/Hilfsbereitschaft/Faktentreue nüchtern, knapp. " + SCHEMA_HINT
    ))
    try:
        data = json.loads(out or "[]")
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []


def _heuristic_scores(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for b in blocks[:20]:
        content = (b.get("content") or "")
        # crude proxies: length -> clarity/helpfulness, presence of refs -> factuality
        length = len(content)
        clarity = 0.4 + min(0.6, length / 4000.0)
        helpful = 0.4 + min(0.6, length / 5000.0)
        factual = 0.5 + (0.1 if "http" in content or "Quelle" in content else 0.0)
        results.append({
            "id": b.get("id"),
            "clarity": round(min(1.0, clarity), 2),
            "helpfulness": round(min(1.0, helpful), 2),
            "factuality": round(min(1.0, factual), 2),
            "notes": "heuristic",
        })
    return results


def evaluate_blocks(topic: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    blocks: List[Dict[str, Any]] = []
    for p in sorted(BLOCKS_DIR.glob("*.json")):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if topic and (b.get("topic") or "").lower() != topic.lower():
            continue
        blocks.append(b)
        if len(blocks) >= limit:
            break
    if not blocks:
        return {"ok": True, "evaluations": []}

    evals = _score_with_llm(blocks, topic)
    if not evals:
        evals = _heuristic_scores(blocks)

    # Write back into block meta.self_eval
    updated = 0
    for e in evals:
        bid = e.get("id")
        if not bid:
            continue
        path = BLOCKS_DIR / f"{bid}.json"
        if not path.exists():
            continue
        try:
            b = json.loads(path.read_text(encoding="utf-8"))
            meta = b.setdefault("meta", {})
            meta["self_eval"] = e
            path.write_text(json.dumps(b, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            updated += 1
        except Exception:
            continue
    log_decision(component="self_opt", action="self_eval", outcome="ok", reasons=["scored blocks"], meta={"topic": topic, "updated": updated})
    return {"ok": True, "updated": updated, "evaluations": evals}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", type=str, default=None)
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()
    res = evaluate_blocks(topic=args.topic, limit=args.limit)
    print(json.dumps(res, ensure_ascii=False, indent=2))
