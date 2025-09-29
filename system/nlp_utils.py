#!/usr/bin/env python3
from __future__ import annotations
import re
from collections import Counter
from typing import List, Dict, Any

# A minimal German/English stopword set; can be extended later
STOPWORDS = set(
    [
        # German
        "der","die","das","und","oder","ein","eine","einer","einem","eines","ist","sind","war","waren","wird","werden","zu","mit","auf","für","von","im","in","an","am","als","auch","so","dass","da","es","sie","er","wir","ihr","ich","man","nur","noch","nicht","kein","keine","ohne","über","unter","zwischen","mehr","weniger","sehr","diese","dieser","dieses","diesem","den","dem","des","beziehungsweise",
        # English
        "the","and","or","a","an","of","for","to","in","on","as","at","by","it","is","are","was","were","be","been","being","that","this","these","those","with","without","from","into","about","over","under","between","very","more","less","no","not","only","just",
    ]
)

WORD_RE = re.compile(r"\b\w{4,}\b", re.UNICODE)


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Extract simple keywords by frequency, excluding stopwords.
    Lowercases for counting, returns unique keywords ordered by frequency.
    """
    words = [w for w in WORD_RE.findall((text or "").lower()) if w not in STOPWORDS]
    if not words:
        return []
    common = Counter(words).most_common(max_keywords)
    return [w for w, _ in common]


def enrich_block(block: Dict[str, Any]) -> Dict[str, Any]:
    """Add semantic keywords and normalized tags to a block in-place.
    - meta.keywords: top keywords (title-cased for readability)
    - tags: merge existing tags with derived ones (lower-case), incl. topic and provenance markers.
    """
    meta = block.setdefault("meta", {})
    content = str(block.get("content") or "")
    topic = str(block.get("topic") or "").strip()
    provenance = str(meta.get("provenance") or "").strip()

    # Keywords
    kws = extract_keywords(content, max_keywords=10)
    meta["keywords"] = [k.title() for k in kws]

    # Tags (lowercase)
    tags = set((block.get("tags") or []) + (meta.get("tags") or []))
    # From keywords
    for k in kws:
        tags.add(k.lower())
    # From topic
    if topic:
        tags.add(topic.lower())
    # From provenance
    if provenance == "auto_reflection":
        tags.update(["reflection", "auto"])
    # Write back normalized
    meta["tags"] = sorted(t for t in tags if t)
    # Keep top-level tags also (optional)
    block["tags"] = sorted(t for t in tags if t)
    return block
