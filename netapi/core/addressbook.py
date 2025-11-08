from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import re

# Reuse the same file used elsewhere
ADDRBOOK_PATH = Path(__file__).resolve().parents[2] / "memory" / "index" / "addressbook.json"
BLOCKS_ROOT = Path(__file__).resolve().parents[2] / "memory" / "long_term" / "blocks"


def _load() -> Dict[str, Any]:
    try:
        if ADDRBOOK_PATH.exists():
            return json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8") or "{}")
    except Exception:
        pass
    return {"blocks": []}


def _normalize_blocks(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("blocks"), list):
        return data.get("blocks") or []
    # legacy schema not needed here; router already migrates; keep fallback empty
    return []


def _topic_from_msg(msg: str) -> str:
    t = (msg or "").strip()
    # remove common German question heads
    heads = [
        r"^was\s+wei[ßs]t\s+du\s+über\s+",
        r"^erzähl\s+mir\s+etwas\s+über\s+",
        r"^wer\s+ist\s+",
        r"^was\s+ist\s+",
    ]
    low = t.lower()
    for h in heads:
        try:
            if re.match(h, low):
                # strip same length from original to keep case
                n = len(re.match(h, low).group(0))  # type: ignore
                return t[n:].strip().strip('?!. ').strip()
        except Exception:
            continue
    return t.strip('?!. ').strip()


def extract_topic_from_message(msg: str) -> str:
    return _topic_from_msg(msg)


def build_topic_paths(topic: str, msg: str = "") -> List[str]:
    topic = (topic or "").strip()
    if not topic:
        return []
    parts: List[str] = []
    low = (msg or topic).lower()
    # simple heuristics for media series
    if ("serie" in low) or ("staffel" in low):
        parts = ["Multimedia", "Serien", topic]
    else:
        parts = ["Wissen", "Allgemein", topic]
    return ["/".join(parts)]


def suggest_topic_paths(user_msg: str) -> List[str]:
    topic = extract_topic_from_message(user_msg)
    return build_topic_paths(topic, user_msg)


def find_paths_for_topic(topic: str) -> List[str]:
    topic_norm = (topic or "").strip().lower()[:120]
    data = _load()
    blocks = _normalize_blocks(data)
    paths: List[str] = []
    for b in blocks:
        try:
            t = str(b.get("topic") or "").strip().lower()[:120]
            if t != topic_norm:
                continue
            p = str(b.get("path") or "").strip()
            if not p:
                continue
            # Derive topic_path from stored file path
            # memory/long_term/blocks/<topic_path>/<block>.json
            try:
                rel = Path(p)
                if not rel.is_absolute():
                    rel = BLOCKS_ROOT / rel
                rel = rel.resolve()
                if BLOCKS_ROOT in rel.parents:
                    tp = str(rel.parent.relative_to(BLOCKS_ROOT)).replace("\\", "/")
                    if tp:
                        paths.append(tp)
            except Exception:
                continue
        except Exception:
            continue
    # De-duplicate, keep order
    seen = set()
    out: List[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def find_blocks_for_topic(topic: str) -> List[str]:
    topic_norm = (topic or "").strip().lower()[:120]
    data = _load()
    blocks = _normalize_blocks(data)
    ids: List[str] = []
    for b in blocks:
        try:
            t = str(b.get("topic") or "").strip().lower()[:120]
            if t != topic_norm:
                continue
            bid = str(b.get("block_id") or "").strip()
            if bid:
                ids.append(bid)
            else:
                # derive from path
                p = str(b.get("path") or "").strip()
                if p:
                    ids.append(Path(p).stem)
        except Exception:
            continue
    # de-dup
    seen = set()
    out: List[str] = []
    for i in ids:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def register_block_for_topic(topic_path: str, block_id: str) -> None:
    try:
        data = _load()
        blocks = _normalize_blocks(data)
        entry = {
            "topic": topic_path.split('/')[-1] if '/' in topic_path else topic_path,
            "block_id": block_id,
            "path": f"{topic_path}/{block_id}.json",
            "source": "",
            "timestamp": None,
            "rating": 0,
        }
        # append if not exists
        exists = False
        for b in blocks:
            if b.get("topic") == entry["topic"] and (b.get("block_id") == block_id):
                exists = True
                break
        if not exists:
            blocks.append(entry)
        ADDRBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
        ADDRBOOK_PATH.write_text(json.dumps({"blocks": blocks}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # best effort
        pass
