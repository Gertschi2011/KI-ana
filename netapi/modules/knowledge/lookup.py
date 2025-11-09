"""Utilities for fetching up-to-date knowledge snippets from web/digest blocks."""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from netapi import memory_store as _mem  # type: ignore
except Exception:  # pragma: no cover - fallback dummy
    _mem = None  # type: ignore

WEB_TAGS = {"web", "digest", "news", "auto", "crawl"}


def _is_web_block(block: Dict[str, Any]) -> bool:
    tags = block.get("tags") or []
    if isinstance(tags, list):
        tags_normalized = {str(t).strip().lower() for t in tags if str(t).strip()}
        if tags_normalized & WEB_TAGS:
            return True
    source = str(block.get("source", "")).lower()
    if any(tag in source for tag in WEB_TAGS):
        return True
    title = str(block.get("title", "")).lower()
    if "digest" in title or "web" in title:
        return True
    return False


def lookup_web_blocks(question: str, *, limit: int = 3, min_score: float = 0.1) -> List[Dict[str, Any]]:
    """Return relevant memory blocks tagged as web/digest for the given question."""
    if not question or not _mem:
        return []
    try:
        hits = _mem.search_blocks(query=str(question), top_k=limit * 4, min_score=min_score)
    except Exception:
        return []

    blocks: List[Dict[str, Any]] = []
    for bid, score in hits:
        try:
            blk = _mem.get_block(bid) or {}
        except Exception:
            continue
        if not blk or not _is_web_block(blk):
            continue
        summary = str(blk.get("content") or blk.get("summary") or "").strip()
        if not summary:
            continue
        blocks.append({
            "id": blk.get("id", bid),
            "title": blk.get("title", "Unbenannt"),
            "content": summary,
            "source": blk.get("source", ""),
            "score": float(score),
        })
        if len(blocks) >= limit:
            break
    return blocks


def blocks_to_prompt(blocks: List[Dict[str, Any]]) -> str:
    if not blocks:
        return ""
    lines = []
    for blk in blocks:
        title = str(blk.get("title") or "Unbenannt").strip()
        snippet = str(blk.get("content") or "").strip()
        snippet = snippet[:600]
        score = blk.get("score")
        score_str = f"{score:.2f}" if isinstance(score, (int, float)) else "?"
        lines.append(f"- {title} (Score {score_str}): {snippet}")
    return "\n".join(lines)


def lookup_web_context(question: str, *, limit: int = 3, min_score: float = 0.1) -> str:
    """Return a formatted snippet with recent web/digest context for the question."""
    blocks = lookup_web_blocks(question, limit=limit, min_score=min_score)
    return blocks_to_prompt(blocks)

