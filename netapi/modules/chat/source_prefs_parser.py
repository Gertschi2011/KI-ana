from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from netapi.modules.memory.schemas import normalize_domain


_NAME_MAP: Dict[str, str] = {
    "der standard": "derstandard.at",
    "standard": "derstandard.at",
    "die presse": "diepresse.com",
    "presse": "diepresse.com",
    "orf": "orf.at",
    "apa": "apa.at",
    "krone": "krone.at",
    "kronen zeitung": "krone.at",
    "kurier": "kurier.at",
}


_BLOCK_HINTS = ("keine", "nicht", "ohne", "block", "sperr", "bitte keine")


@dataclass(frozen=True)
class SourcePrefsParseResult:
    preferred_add: List[str]
    blocked_add: List[str]
    notes: Optional[str] = None


_DOMAIN_RE = re.compile(r"\b([a-z0-9-]+\.)+[a-z]{2,}\b", re.IGNORECASE)


def _extract_domains(text: str) -> List[str]:
    found = []
    for match in _DOMAIN_RE.findall(text or ""):
        dom = normalize_domain(match)
        if dom and dom not in found:
            found.append(dom)
    return found


def _extract_named_sources(text: str) -> List[str]:
    low = (text or "").lower()
    hits = []
    for name, dom in _NAME_MAP.items():
        if name in low:
            nd = normalize_domain(dom)
            if nd and nd not in hits:
                hits.append(nd)
    return hits


def parse_source_prefs_user_text(text: str) -> SourcePrefsParseResult:
    """Parse a user's free-form answer into preferred/blocked domain additions.

    Supports:
    - "ORF, Der Standard, APA"
    - "Bitte keine Krone"
    - "Nimm nur seriöse" (stored as notes)
    """

    raw = (text or "").strip()
    low = raw.lower()

    domains = _extract_domains(raw)
    names = _extract_named_sources(raw)
    candidates = []
    for d in [*domains, *names]:
        if d and d not in candidates:
            candidates.append(d)

    is_blockish = any(h in low for h in _BLOCK_HINTS)

    preferred: List[str] = []
    blocked: List[str] = []

    if candidates:
        if is_blockish:
            blocked = candidates
        else:
            preferred = candidates

    notes: Optional[str] = None
    if not preferred and not blocked:
        # Accept policy-ish answers like "nur seriöse"
        if any(token in low for token in ("seriös", "serioes", "verläss", "zuverläss", "trusted")):
            notes = raw

    return SourcePrefsParseResult(preferred_add=preferred, blocked_add=blocked, notes=notes)


def merge_prefs(
    *,
    preferred_existing: List[str],
    blocked_existing: List[str],
    parsed: SourcePrefsParseResult,
) -> Tuple[List[str], List[str]]:
    preferred = list(preferred_existing or [])
    blocked = list(blocked_existing or [])

    for dom in parsed.preferred_add or []:
        nd = normalize_domain(dom)
        if nd and nd not in preferred:
            preferred.append(nd)
        if nd and nd in blocked:
            blocked = [b for b in blocked if b != nd]

    for dom in parsed.blocked_add or []:
        nd = normalize_domain(dom)
        if nd and nd not in blocked:
            blocked.append(nd)
        if nd and nd in preferred:
            preferred = [p for p in preferred if p != nd]

    return preferred, blocked
