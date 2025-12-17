from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse


_STOPWORDS = {
    # de
    "der",
    "die",
    "das",
    "ein",
    "eine",
    "einer",
    "eines",
    "und",
    "oder",
    "aber",
    "mit",
    "ohne",
    "für",
    "fuer",
    "von",
    "im",
    "in",
    "am",
    "an",
    "auf",
    "zu",
    "über",
    "ueber",
    "bei",
    "aus",
    "ist",
    "sind",
    "war",
    "wird",
    "wurden",
    "werden",
    "heute",
    "gestern",
    "morgen",
    "aktuell",
    "news",
    "nachrichten",
    "neuesten",
    "neueste",
    "latest",
    # en
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "with",
    "without",
    "for",
    "from",
    "in",
    "on",
    "at",
    "to",
    "about",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
}


_SERVICE_PR_HOST_HINTS = {
    "prnewswire",
    "globenewswire",
    "businesswire",
    "newswire",
    "presseportal",
}


_SERVICE_PR_PATH_HINTS = (
    "impressum",
    "kontakt",
    "about",
    "ueber-uns",
    "über-uns",
    "privacy",
    "datenschutz",
    "agb",
    "terms",
    "bedingungen",
    "jobs",
    "karriere",
    "career",
    "press",
    "presse",
    "newsletter",
    "subscribe",
    "pricing",
    "preise",
    "produkt",
    "product",
    "service",
    "services",
)


_NEWS_WHOCARES_KEYWORDS = (
    "presseaussendung",
    "press release",
    "presse",
    "newsletter",
    "podcast",
    "audio",
    "barrierefrei",
    "service",
    "infoportal",
    "amtsblatt",
    "wir starten",
    "neues feature",
    "launch",
    "kündigt",
    "ankuendigt",
)


_NEWS_WHOCARES_DOMAIN_HINTS = (
    "parlament.gv.at",
)


_CATEGORY_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("politik", ("regierung", "parlament", "wahl", "minister", "kanzler", "präsident", "praesident", "koalition", "partei")),
    ("wirtschaft", ("börse", "boerse", "inflation", "zins", "markt", "aktie", "aktien", "konzern", "firma", "unternehmen", "bank")),
    ("sport", ("bundesliga", "champions", "spiel", "match", "tor", "trainer", "liga", "wm", "em")),
    ("technik", ("ki", "ai", "künstliche", "kuenstliche", "software", "app", "chip", "cyber", "hacker")),
    ("gesundheit", ("covid", "grippe", "gesundheit", "krankenhaus", "impfung", "virus", "medizin")),
    ("klima", ("klima", "wetter", "sturm", "hochwasser", "umwelt", "co2", "temperatur")),
    ("justiz", ("polizei", "gericht", "prozess", "anklage", "verhaft", "kriminal", "tat")),
    ("kultur", ("film", "musik", "theater", "kunst", "festival", "buch")),
]


def _domain_from_url(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        host = urlparse(str(url)).netloc.lower().strip()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def _tokenize(text: str) -> List[str]:
    cleaned = re.sub(r"[^\w\s-]", " ", str(text or "").lower())
    parts = re.split(r"[\s_-]+", cleaned)
    out: List[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) <= 2:
            continue
        if p in _STOPWORDS:
            continue
        out.append(p)
    return out


def _is_service_or_pr_page(*, url: str, title: str, domain: str) -> bool:
    low_title = (title or "").lower()
    low_url = (url or "").lower()
    if any(h in domain for h in _SERVICE_PR_HOST_HINTS):
        return True
    if any(h in low_url for h in _SERVICE_PR_PATH_HINTS):
        return True
    if any(h in low_title for h in ("presse", "press", "impressum", "kontakt", "jobs", "karriere")):
        return True
    return False


def categorize_result(*, title: str, snippet: str, url: str) -> str:
    text = " ".join([str(title or ""), str(snippet or ""), str(url or "")]).lower()
    for cat, keys in _CATEGORY_RULES:
        if any(k in text for k in keys):
            return cat
    return "sonstiges"


def score_result(*, query: str, title: str, snippet: str, url: str, published: str = "") -> float:
    q_tokens = set(_tokenize(query))
    title_low = (title or "").lower()
    snippet_low = (snippet or "").lower()

    score = 0.0

    for t in q_tokens:
        if t in title_low:
            score += 2.0
        elif t in snippet_low:
            score += 1.0

    # small recency hint if date exists (provider date strings are inconsistent)
    if (published or "").strip():
        score += 0.25

    domain = _domain_from_url(url)
    if _is_service_or_pr_page(url=url, title=title, domain=domain):
        score -= 3.0

    return score


@dataclass(frozen=True)
class RelevanceMeta:
    applied: bool
    filtered_out_count: int
    top_categories: List[str]


@dataclass(frozen=True)
class ServicePenaltyMeta:
    applied: bool
    penalized_examples: List[Dict[str, str]]


def apply_relevance_reorder(
    results: Sequence[Dict[str, Any]],
    *,
    query: str,
    top_n_considered: int = 10,
    low_score_threshold: float = 0.25,
) -> Tuple[List[Dict[str, Any]], RelevanceMeta]:
    """Reorder-only relevance scoring.

    - Never drops items; only reorders.
    - Annotates each item with `_relevance_score` and `_relevance_category`.
    """

    items: List[Dict[str, Any]] = [dict(r) for r in (results or [])]
    if not items:
        return [], RelevanceMeta(applied=False, filtered_out_count=0, top_categories=[])

    scored: List[Tuple[int, float, Dict[str, Any]]] = []
    for idx, it in enumerate(items):
        title = str(it.get("title") or "")
        snippet = str(it.get("snippet") or it.get("description") or "")
        url = str(it.get("url") or "")
        published = str(it.get("published") or it.get("date") or "")

        category = categorize_result(title=title, snippet=snippet, url=url)
        s = score_result(query=query, title=title, snippet=snippet, url=url, published=published)

        it["_relevance_score"] = float(s)
        it["_relevance_category"] = category
        scored.append((idx, s, it))

    # Stable sort by score desc, then original position.
    ordered = sorted(scored, key=lambda x: (-float(x[1]), x[0]))

    # For transparency: "applied" means we executed the pass for this request.
    applied = True

    top_items = [x[2] for x in ordered[: max(1, int(top_n_considered))]]
    filtered_out_count = 0
    for it in top_items:
        try:
            if float(it.get("_relevance_score") or 0.0) < float(low_score_threshold):
                filtered_out_count += 1
        except Exception:
            continue

    cats = [str(it.get("_relevance_category") or "sonstiges") for it in top_items]
    counts = Counter(cats)
    top_categories = [c for c, _n in counts.most_common(3) if c]

    return [x[2] for x in ordered], RelevanceMeta(applied=bool(applied), filtered_out_count=int(filtered_out_count), top_categories=top_categories)


def _title_signature(title: str) -> List[str]:
    return _tokenize(title)


def _jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    sa = set(a)
    sb = set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    inter = len(sa.intersection(sb))
    union = len(sa.union(sb))
    return float(inter) / float(union) if union else 0.0


def apply_title_dedup_reorder(
    results: Sequence[Dict[str, Any]],
    *,
    top_n: int = 10,
    similarity_threshold: float = 0.78,
) -> Tuple[List[Dict[str, Any]], bool]:
    """Reorder-only dedup/cluster by title similarity.

    Keeps the earliest/highest-ranked item for each cluster in the top_n window
    and pushes near-duplicates behind the top_n block.
    """

    items: List[Dict[str, Any]] = [dict(r) for r in (results or [])]
    if len(items) <= 1:
        return items, False

    head = items[: max(1, int(top_n))]
    tail = items[max(1, int(top_n)) :]

    kept: List[Dict[str, Any]] = []
    dupes: List[Dict[str, Any]] = []
    kept_sigs: List[List[str]] = []
    kept_cluster_ids: List[int] = []
    next_cluster_id = 1

    for it in head:
        title = str(it.get("title") or "")
        sig = _title_signature(title)
        is_dupe = False
        matched_cluster_id: Optional[int] = None
        for prev in kept_sigs:
            j = _jaccard(sig, prev)
            if j >= float(similarity_threshold):
                is_dupe = True
                try:
                    matched_cluster_id = kept_cluster_ids[kept_sigs.index(prev)]
                except Exception:
                    matched_cluster_id = None
                break
        if is_dupe:
            it["_dedup_clustered"] = True
            it["_dedup_cluster_id"] = matched_cluster_id or 0
            dupes.append(it)
        else:
            it["_dedup_clustered"] = False
            it["_dedup_cluster_id"] = next_cluster_id
            kept.append(it)
            kept_sigs.append(sig)
            kept_cluster_ids.append(next_cluster_id)
            next_cluster_id += 1

    # Ensure the top_n window stays filled with non-duplicate items when possible.
    # This pushes clustered duplicates behind the top_n boundary (reorder-only).
    top_n_int = max(1, int(top_n))
    backfill_needed = max(0, top_n_int - len(kept))
    out_head = kept + tail[:backfill_needed]
    out_tail = tail[backfill_needed:]
    out = out_head + dupes + out_tail
    # For transparency: "applied" means pass executed.
    applied = True
    return out, bool(applied)


def apply_news_penalty_reorder(
    results: Sequence[Dict[str, Any]],
    *,
    query: str,
    top_n_considered: int = 10,
) -> Tuple[List[Dict[str, Any]], bool]:
    """Reorder-only "who-cares" penalty pass.

    - Never drops items; only reorders.
    - Adds `_news_penalty` numeric field (<0 means downrank)
    """

    items: List[Dict[str, Any]] = [dict(r) for r in (results or [])]
    if not items:
        return [], False

    query_low = str(query or "").lower()

    scored: List[Tuple[int, float, Dict[str, Any]]] = []
    for idx, it in enumerate(items):
        title = str(it.get("title") or "")
        snippet = str(it.get("snippet") or it.get("description") or "")
        url = str(it.get("url") or "")
        domain = _domain_from_url(url)

        text = f"{title} {snippet} {url}".lower()
        penalty = 0.0

        if any(d == domain or domain.endswith("." + d) for d in _NEWS_WHOCARES_DOMAIN_HINTS):
            penalty -= 4.0

        if any(k in text for k in _NEWS_WHOCARES_KEYWORDS):
            penalty -= 2.0

        # If user asked for "Nachrichten" and the item screams service/PR, penalize a bit more.
        if ("nachrichten" in query_low or "news" in query_low) and ("presse" in text or "newsletter" in text or "amtsblatt" in text):
            penalty -= 1.5

        it["_news_penalty"] = float(penalty)
        base = float(it.get("_relevance_score") or 0.0)
        scored.append((idx, base + penalty, it))

    ordered = sorted(scored, key=lambda x: (-float(x[1]), x[0]))
    # applied means pass ran
    applied = True

    # Additionally, if we have enough results, force strong-penalty items out of top window.
    try:
        top_n = max(1, int(top_n_considered))
        head = [x[2] for x in ordered[:top_n]]
        tail = [x[2] for x in ordered[top_n:]]
        strong = [it for it in head if float(it.get("_news_penalty") or 0.0) <= -4.0]
        rest = [it for it in head if it not in strong]
        if strong:
            ordered_items = rest + tail + strong
            return ordered_items, bool(applied)
    except Exception:
        pass

    return [x[2] for x in ordered], bool(applied)


def _parse_relative_age_hours(published: str) -> Optional[float]:
    """Best-effort parse of relative age strings into hours."""

    s = str(published or "").strip().lower()
    if not s:
        return None

    # Normalize German umlauts for matching.
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")

    m = re.search(r"\bvor\s+(\d+)\s+(minute|minuten|stunde|stunden|tag|tage|woche|wochen|monat|monate|jahr|jahre)\b", s)
    if not m:
        m = re.search(r"\b(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\s+ago\b", s)
    if not m:
        return None

    try:
        n = int(m.group(1))
    except Exception:
        return None

    unit = str(m.group(2))
    if unit.startswith("minute") or unit.startswith("minut"):
        return float(n) / 60.0
    if unit.startswith("stunde") or unit.startswith("hour"):
        return float(n)
    if unit.startswith("tag") or unit.startswith("day"):
        return float(n) * 24.0
    if unit.startswith("woche") or unit.startswith("week"):
        return float(n) * 24.0 * 7.0
    if unit.startswith("monat") or unit.startswith("month"):
        return float(n) * 24.0 * 30.0
    if unit.startswith("jahr") or unit.startswith("year"):
        return float(n) * 24.0 * 365.0
    return None


def apply_service_penalty_reorder(
    results: Sequence[Dict[str, Any]],
    *,
    query: str,
    top_n_considered: int = 10,
) -> Tuple[List[Dict[str, Any]], ServicePenaltyMeta]:
    """Phase 4: reorder-only service-noise penalty.

    Builds on the existing `_news_penalty` logic, adds stale detection, reasons,
    and a small `penalized_examples` list for meta.
    """

    items: List[Dict[str, Any]] = [dict(r) for r in (results or [])]
    if not items:
        return [], ServicePenaltyMeta(applied=False, penalized_examples=[])

    # Start with existing penalty pass.
    penalized, _applied = apply_news_penalty_reorder(items, query=query, top_n_considered=top_n_considered)

    scored: List[Tuple[int, float, Dict[str, Any]]] = []
    for idx, it in enumerate(penalized):
        published = str(it.get("published") or it.get("date") or "")
        age_h = _parse_relative_age_hours(published)
        extra_penalty = 0.0
        reason = ""
        if age_h is not None and age_h > 48.0:
            extra_penalty -= 3.0
            reason = "stale"
        it["_service_penalty"] = float(float(it.get("_news_penalty") or 0.0) + extra_penalty)
        it["_service_penalty_reason"] = str(reason or ("service_noise" if float(it.get("_news_penalty") or 0.0) < 0 else ""))
        base = float(it.get("_relevance_score") or 0.0)
        scored.append((idx, base + float(it.get("_service_penalty") or 0.0), it))

    ordered = sorted(scored, key=lambda x: (-float(x[1]), x[0]))
    out = [x[2] for x in ordered]

    examples: List[Dict[str, str]] = []
    for it in out[: max(1, int(top_n_considered))]:
        if float(it.get("_service_penalty") or 0.0) < 0.0:
            examples.append(
                {
                    "title": str(it.get("title") or "")[:140],
                    "domain": _domain_from_url(str(it.get("url") or "")) or "",
                    "reason": str(it.get("_service_penalty_reason") or "service_noise"),
                }
            )
        if len(examples) >= 3:
            break

    return out, ServicePenaltyMeta(applied=True, penalized_examples=examples)


def apply_interest_reorder(
    results: Sequence[Dict[str, Any]],
    *,
    profile: Optional[Dict[str, Any]],
    top_n_considered: int = 10,
) -> Tuple[List[Dict[str, Any]], bool, List[str]]:
    """Phase 4: reorder-only interest pass based on interest_profile weights."""

    items: List[Dict[str, Any]] = [dict(r) for r in (results or [])]
    if not items or not isinstance(profile, dict):
        return items, False, []

    cat_w = profile.get("category_weights") if isinstance(profile.get("category_weights"), dict) else {}
    dom_w = profile.get("domain_affinity") if isinstance(profile.get("domain_affinity"), dict) else {}
    if not cat_w and not dom_w:
        return items, False, []

    def _clamp(v: float, lo: float, hi: float) -> float:
        if v < lo:
            return lo
        if v > hi:
            return hi
        return v

    scored: List[Tuple[int, float, Dict[str, Any]]] = []
    for idx, it in enumerate(items):
        base = float(it.get("_relevance_score") or 0.0)
        domain = _domain_from_url(str(it.get("url") or ""))
        category = str(it.get("_relevance_category") or it.get("category") or "").strip().lower()

        dom_delta = 0.0
        cat_delta = 0.0
        try:
            if domain and domain in dom_w:
                dom_delta = float(dom_w.get(domain) or 0.0)
        except Exception:
            dom_delta = 0.0
        try:
            if category and category in cat_w:
                cat_delta = float(cat_w.get(category) or 0.0)
        except Exception:
            cat_delta = 0.0

        dom_delta = _clamp(dom_delta, -0.2, 0.25)
        cat_delta = _clamp(cat_delta, -0.2, 0.25)
        factor = _clamp(1.0 + dom_delta + cat_delta, 0.8, 1.25)
        interest_score = float(base) * float(factor)

        it["_interest_factor"] = float(factor)
        it["_interest_score"] = float(interest_score)
        scored.append((idx, interest_score, it))

    ordered = sorted(scored, key=lambda x: (-float(x[1]), x[0]))
    out = [x[2] for x in ordered]

    cats = [str(it.get("_relevance_category") or "sonstiges") for it in out[: max(1, int(top_n_considered))]]
    counts = Counter(cats)
    top_categories = [c for c, _n in counts.most_common(3) if c]
    return out, True, top_categories


def build_news_cards_from_results(
    results: Sequence[Dict[str, Any]],
    *,
    limit: int = 7,
) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    for it in (results or [])[: max(1, int(limit))]:
        url = str(it.get("url") or "")
        title = str(it.get("title") or "")
        if not url or not title:
            continue
        domain = _domain_from_url(url)
        source_label = str(it.get("source") or it.get("publisher") or domain or "")
        published = str(it.get("published") or it.get("date") or "")
        snippet = str(it.get("snippet") or it.get("description") or "")
        cards.append(
            {
                "title": title,
                "source": source_label,
                "label": source_label,
                "domain": domain,
                "url": url,
                "date": published,
                "published": published,
                "summary": snippet,
                "category": it.get("_relevance_category"),
                "relevance": it.get("_relevance_score"),
                "cluster_id": it.get("_dedup_cluster_id"),
                "dedup_clustered": it.get("_dedup_clustered"),
                "penalty": it.get("_news_penalty"),
            }
        )
    return cards
