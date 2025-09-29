#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = Path.home() / "ki_ana"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"
INDEX_DIR = BASE_DIR / "memory" / "index"
INDEX_PATH = INDEX_DIR / "blocks_index.json"
META_PATH = INDEX_DIR / "blocks_meta.json"

_token_re = re.compile(r"[A-Za-z0-9ÄÖÜäöüß]+", re.UNICODE)

def _tok(s: str) -> List[str]:
    return [m.group(0).lower() for m in _token_re.finditer(s or "")]


def _load_block(f: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None


def build_index() -> Dict[str, Any]:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    postings: Dict[str, List[str]] = {}
    meta: Dict[str, Dict[str, Any]] = {}
    count_docs = 0
    for f in sorted(BLOCKS_DIR.glob("*.json")):
        b = _load_block(f)
        if not b:
            continue
        h = b.get("hash") or f.stem
        topic = (b.get("topic") or b.get("title") or "").strip()
        tags = b.get("tags") or []
        source = b.get("source") or ""
        text = " ".join([b.get("title") or "", b.get("content") or ""]).strip()
        # meta table
        meta[h] = {
            "hash": h,
            "title": b.get("title") or "",
            "topic": topic,
            "tags": tags,
            "source": source,
            "len": len(text),
        }
        # field tokens
        terms = set(_tok(text))
        for t in terms:
            postings.setdefault(t, []).append(h)
        # fast lookups for tags/topic/source
        for t in [*[_t.lower() for _t in tags], topic.lower(), str(source).lower()]:
            if not t:
                continue
            postings.setdefault(f"__tag__:{t}", []).append(h)
        count_docs += 1
    # dedup postings lists
    for k, lst in postings.items():
        postings[k] = sorted(list(dict.fromkeys(lst)))
    INDEX_PATH.write_text(json.dumps(postings, ensure_ascii=False, indent=0, separators=(",", ":")), encoding="utf-8")
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=0, separators=(",", ":")), encoding="utf-8")
    return {"ok": True, "docs": count_docs, "terms": len(postings)}


def _ensure_index_loaded() -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, Any]]]:
    if not INDEX_PATH.exists() or not META_PATH.exists():
        build_index()
    try:
        postings: Dict[str, List[str]] = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        meta: Dict[str, Dict[str, Any]] = json.loads(META_PATH.read_text(encoding="utf-8"))
        if not isinstance(postings, dict) or not isinstance(meta, dict):
            raise ValueError("index files invalid")
        return postings, meta
    except Exception:
        return {}, {}


def search_blocks(topic: Optional[str] = None,
                  tags: Optional[List[str]] = None,
                  source: Optional[str] = None,
                  text: Optional[str] = None,
                  limit: int = 10) -> List[Dict[str, Any]]:
    postings, meta = _ensure_index_loaded()
    if not postings:
        return []
    # gather candidate doc IDs
    candidates: Optional[set] = None
    def _intersect(ids: List[str]):
        nonlocal candidates
        s = set(ids)
        candidates = s if candidates is None else (candidates & s)
    if topic:
        _intersect(postings.get(f"__tag__:{topic.lower()}", []))
    if source:
        _intersect(postings.get(f"__tag__:{source.lower()}", []))
    if tags:
        for t in [t for t in tags if t]:
            _intersect(postings.get(f"__tag__:{t.lower()}", []))
    if text:
        # simple AND over terms
        for t in _tok(text):
            _intersect(postings.get(t, []))
    # if nothing filtered, take all
    cand_ids = list(candidates) if candidates is not None else list(meta.keys())
    # score (very simple): matches count + title boost
    q_terms = set(_tok(" ".join([text or "", topic or "", " ".join(tags or []), source or ""])) )
    scored: List[Tuple[float, str]] = []
    for hid in cand_ids:
        m = meta.get(hid) or {}
        doc_terms = set([*(_tok(m.get("title") or "")), *(_tok(m.get("topic") or "")), *(_tok(" ".join(m.get("tags") or [])))])
        overlap = len(q_terms & doc_terms)
        score = overlap + (1.0 if (topic and topic.lower() in (m.get("topic") or "").lower()) else 0.0)
        scored.append((score, hid))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for _, hid in scored[: max(1, int(limit))]:
        out.append(meta.get(hid) or {"hash": hid})
    return out


def get_context_for_query(query: str, max_chars: int = 1200) -> str:
    postings, meta = _ensure_index_loaded()
    if not meta:
        return ""
    hits = search_blocks(text=query, limit=8)
    snippets: List[str] = []
    for h in hits:
        hid = h.get("hash")
        f = BLOCKS_DIR / f"{hid}.json"
        b = _load_block(f) or {}
        title = b.get("title") or h.get("title") or ""
        content = (b.get("content") or "").strip()
        snippet = (content[: max_chars // 4] + ("…" if len(content) > max_chars // 4 else ""))
        snippets.append(f"- {title}: {snippet}")
        if len("\n".join(snippets)) > max_chars:
            break
    return "\n".join(snippets)
