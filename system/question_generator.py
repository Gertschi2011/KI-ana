from __future__ import annotations
import json
import random
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path.home() / "ki_ana"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"


def _load_blocks() -> List[Dict[str, Any]]:
    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    out: List[Dict[str, Any]] = []
    for p in BLOCKS_DIR.glob("*.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


TEMPLATES = [
    "Wie wirkt sich dies auf Privatsphäre und Sicherheit aus?",
    "Wer profitiert am meisten und wer trägt die Risiken?",
    "Welche Alternativen existieren und warum sind sie besser/schlechter?",
    "Welche langfristigen Folgen sind zu erwarten?",
    "Welche Evidenz stützt diese Aussage und was fehlt noch?",
    "Welche Stakeholder sind betroffen und wie kann man sie einbinden?",
]


def _make_question(block: Dict[str, Any]) -> str:
    title = (block.get("title") or "").strip()
    topic = (block.get("topic") or "").strip()
    base = random.choice(TEMPLATES)
    if title:
        return f"Zu '{title}': {base}"
    if topic:
        return f"Zum Thema '{topic}': {base}"
    return base


def generate_questions_from_blocks(num: int = 5) -> List[Dict[str, Any]]:
    blocks = _load_blocks()
    if not blocks:
        return []
    random.shuffle(blocks)
    picks = blocks[: max(1, int(num))]
    out: List[Dict[str, Any]] = []
    for b in picks:
        out.append({
            "block_id": b.get("id"),
            "title": b.get("title"),
            "question": _make_question(b),
        })
    return out
