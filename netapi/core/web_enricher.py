from __future__ import annotations

import logging
import os
import json
import re
import asyncio
import random
import threading
import time
import httpx
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING
from urllib.parse import quote_plus, urlparse
from zoneinfo import ZoneInfo
try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore
try:
    from system.conflict_resolver import get_trust_score_from_url
except Exception:  # pragma: no cover
    def get_trust_score_from_url(_url: str) -> float:  # type: ignore
        return 0.5
try:
    from netapi.modules.web.news_sources import (  # type: ignore
        NewsSourcePrefs,
        get_news_sources_for_locale,
    )
except Exception:  # pragma: no cover
    NewsSourcePrefs = None  # type: ignore

    def get_news_sources_for_locale(*_args, **_kwargs):  # type: ignore
        return []

try:
    from netapi.core.news_enricher import GlobalNewsLayer  # type: ignore
except Exception:  # pragma: no cover
    GlobalNewsLayer = None  # type: ignore

if TYPE_CHECKING:
    from netapi.core.news_enricher import GlobalNewsLayer as GlobalNewsLayerType  # pragma: no cover
    from netapi.modules.crawler.models import NewsSource as NewsSourceType  # pragma: no cover
else:  # pragma: no cover
    GlobalNewsLayerType = Any
    NewsSourceType = Any

try:  # Settings integration (env over config)
    from netapi.config import settings  # type: ignore
except Exception:  # pragma: no cover
    settings = None  # type: ignore

try:
    from netapi.modules.chat import memory_adapter  # type: ignore
except Exception:  # pragma: no cover
    memory_adapter = None  # type: ignore

try:  # Optional news source integrations
    from netapi.db import SessionLocal  # type: ignore
    from netapi.core.news_sources import get_ranked_sources_for_locale  # type: ignore
    from netapi.modules.crawler.models import NewsSource  # type: ignore
except Exception:  # pragma: no cover
    SessionLocal = None  # type: ignore
    get_ranked_sources_for_locale = None  # type: ignore
    NewsSource = None  # type: ignore
@contextmanager
def _news_source_session():
    if SessionLocal is None:
        yield None
        return
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _fetch_ranked_news_sources(
    country_code: Optional[str],
    locale: Optional[str],
    *,
    tags: Optional[List[str]] = None,
    limit: int = 20,
) -> List[NewsSourceType]:
    if SessionLocal is None or get_ranked_sources_for_locale is None:
        return []
    with _news_source_session() as session:
        if session is None:
            return []
        try:
            return get_ranked_sources_for_locale(
                session,
                country_code,
                locale,
                tags=tags,
                limit=limit,
            )
        except Exception:  # pragma: no cover - defensive
            logger.debug("failed to load ranked news sources", exc_info=True)
            return []


def _news_source_bonus(
    result: Dict[str, Any],
    *,
    news_map: Dict[str, NewsSourceType],
    user_country: Optional[str],
    user_locale: Optional[str],
) -> float:
    domain = _domain_from_url(result.get("url"))
    if not domain:
        return 0.0
    src = news_map.get(domain)
    if not src:
        return 0.0

    trust_value = float(src.trust_score or 0)
    bonus = trust_value / 100.0
    if getattr(src, "is_preferred", False):
        bonus += 4.0
    if user_country and src.country_code and src.country_code.upper() == user_country.upper():
        bonus += 3.0
    if user_locale and src.locale:
        if src.locale.lower() == user_locale.lower():
            bonus += 3.0
        elif src.locale.split("-", 1)[0].lower() == user_locale.split("-", 1)[0].lower():
            bonus += 1.5
    result.setdefault("news_source", {
        "domain": src.domain,
        "trust_score": src.trust_score,
        "is_preferred": src.is_preferred,
        "country_code": src.country_code,
        "locale": src.locale,
        "last_seen_at": src.last_seen_at.isoformat() if src.last_seen_at else None,
    })
    return bonus


def _prioritize_with_news_sources(
    results: List[Dict[str, Any]],
    *,
    news_map: Dict[str, NewsSourceType],
    user_country: Optional[str],
    user_locale: Optional[str],
) -> List[Dict[str, Any]]:
    if not news_map or not results:
        return results

    prioritized: List[Dict[str, Any]] = []
    for entry in results:
        base = float(entry.get("trust_score") or 0.5) * 10.0
        if entry.get("score") is not None:
            try:
                base += float(entry["score"])
            except Exception:
                pass
        bonus = _news_source_bonus(
            entry,
            news_map=news_map,
            user_country=user_country,
            user_locale=user_locale,
        )
        entry["_news_priority"] = base + bonus
        prioritized.append(entry)

    prioritized.sort(key=lambda item: item.get("_news_priority", 0.0), reverse=True)
    return prioritized

logger = logging.getLogger(__name__)


def _parse_serper_results(raw_json: dict) -> list[dict]:
    """Parse Serper response and return normalized organic results.

    Contract:
    - Uses only raw_json['organic']
    - Always returns a uniform result schema:
        {"title": str, "url": str, "snippet": str, "source": "serper", "provider": "serper"}
    - If Serper returns `link`, it is mapped to `url`.
    """

    organic_items = raw_json.get("organic") or []
    if not isinstance(organic_items, list):
        return []

    results: list[dict] = []
    for item in organic_items:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or item.get("link")
        if not url or not str(url).startswith("http"):
            continue
        results.append(
            {
                "title": str(item.get("title") or "Serper Result"),
                "url": str(url),
                "snippet": str(item.get("snippet") or item.get("description") or ""),
                "source": "serper",
                "provider": "serper",
            }
        )
    return results


def _parse_serper_news_results(raw_json: dict) -> list[dict]:
    """Parse Serper News response and return normalized news results.

    Contract:
    - Uses only raw_json['news']
    - Always returns a uniform result schema:
        {"title": str, "url": str, "snippet": str, "source": str, "date": str, "provider": "serper-news"}
    """

    news_items = raw_json.get("news") or []
    if not isinstance(news_items, list):
        return []

    results: list[dict] = []
    for item in news_items:
        if not isinstance(item, dict):
            continue
        url = item.get("link") or item.get("url")
        if not url or not str(url).startswith("http"):
            continue
        published = item.get("date") or item.get("published") or ""
        source = item.get("publisher") or item.get("source") or ""
        if isinstance(source, dict):
            source = source.get("name") or source.get("title") or source.get("domain") or ""
        results.append(
            {
                "title": str(item.get("title") or "News"),
                "url": str(url),
                "snippet": str(item.get("snippet") or item.get("description") or ""),
                "source": str(source) if source is not None else "",
                "date": str(published) if published is not None else "",
                "published": str(published) if published is not None else "",
                "provider": "serper-news",
            }
        )
    return results


async def search_serper(query: str, lang: str, max_results: int) -> List[Dict[str, Any]]:
    """Async Serper web search (Phase 1.1).

    - Uses httpx.AsyncClient
    - Reads SERPER_API_KEY and SERPER_API_ENDPOINT
    - Logs request params, HTTP status, raw and parsed counts
    """

    api_key = os.getenv("SERPER_API_KEY")
    endpoint = os.getenv("SERPER_API_ENDPOINT", "https://google.serper.dev/search")
    if not api_key:
        logger.warning("serper: SERPER_API_KEY missing – cannot perform web search")
        return []

    region = "us"
    if str(lang or "").lower().startswith("de"):
        region = "at"
    payload: Dict[str, Any] = {
        "q": query,
        "num": int(max_results),
        "gl": region,
        "hl": "de" if str(lang or "").lower().startswith("de") else "en",
    }
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    logger.info(
        "serper(async): POST %s query=%r gl=%s hl=%s num=%s",
        endpoint,
        query,
        payload.get("gl"),
        payload.get("hl"),
        payload.get("num"),
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
        logger.info("serper(async): HTTP %s for query=%r", resp.status_code, query)
        resp.raise_for_status()
        data = resp.json() or {}
        if not isinstance(data, dict):
            logger.warning("serper(async): non-dict JSON payload for query=%r", query)
            return []
    except Exception as exc:
        logger.error(
            "serper(async): ERROR for query=%r: %s",
            query,
            exc,
            exc_info=True,
        )
        return []

    organic = data.get("organic") or []
    raw_count = len(organic) if isinstance(organic, list) else 0
    parsed_all = _parse_serper_results(data)
    parsed = parsed_all[: max(0, int(max_results))]
    logger.info(
        "serper(async): raw_organic=%d parsed=%d query=%r",
        raw_count,
        len(parsed),
        query,
    )
    return parsed

DEFAULT_TIMEOUT = 12.0
DEFAULT_MAX_PAGES = 3
DEFAULT_MAX_CHARS = 5000
DEFAULT_SEARCH_ENDPOINT = "https://api.duckduckgo.com/"
DEFAULT_SNAPSHOT_ROOT = (
    os.getenv("KIANA_WEB_SNAPSHOT_ROOT") or "/tmp/kiana_web_snapshots"
)

DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 KIanaBot/2.0 "
        "+https://ki-ana.at"
    )
}

EXPLICIT_WEB_OVERRIDE_PATTERNS = [
    "nutze deine websuche",
    "verwende deine websuche",
    "schau im web nach",
    "websuche bitte",
    "bitte nutze die websuche",
    "bitte verwende die websuche",
]

NEWS_KEYWORDS = [
    "news",
    "nachrichten",
    "schlagzeilen",
    "heute in",
    "was ist los in",
    "aktuell in",
    "latest in",
    "breaking news",
    "latest news",
    "breaking",
    "breaking update",
    "breaking updates",
    "latest updates",
    "aktuelle nachrichten",
    "aktuellen nachrichten",
    "neueste nachrichten",
    "neuesten nachrichten",
    "heutige nachrichten",
    "top stories",
    "headline",
    "headlines",
    "presseschau",
    "world news",
    "global news",
    "international news",
    "current events",
    "what's happening",
    "whats happening",
    "was passiert",
    "was passiert gerade",
    "was tut sich",
    "neue entwicklungen",
    "new developments",
    "todays news",
    "today's news",
]

LANG_TO_DEFAULT_COUNTRY: Dict[str, str] = {
    "de": "at",
    "de-at": "at",
    "de-de": "de",
    "en": "us",
    "en-gb": "gb",
    "en-us": "us",
    "ro": "ro",
    "fr": "fr",
    "it": "it",
}

COUNTRY_HINTS: Dict[str, List[str]] = {
    "at": ["österreich", "wien", "linz", "graz", "salzburg"],
    "de": ["deutschland", "berlin", "hamburg", "münchen"],
    "us": ["usa", "vereinigte staaten", "washington dc", "new york"],
    "gb": ["großbritannien", "vereinigtes königreich", "london"],
    "ro": ["rumänien", "bucurești", "bukarest"],
}

COUNTRY_LABELS: Dict[str, str] = {
    "AT": "Österreich",
    "DE": "Deutschland",
    "US": "USA",
    "GB": "Vereinigtes Königreich",
    "RO": "Rumänien",
}

COUNTRY_TIMEZONES: Dict[str, str] = {
    "AT": "Europe/Vienna",
    "DE": "Europe/Berlin",
    "US": "America/New_York",
    "GB": "Europe/London",
    "RO": "Europe/Bucharest",
}

DEFAULT_TIMEZONE = "UTC"

GREETING_PREFIXES: Tuple[str, ...] = (
    "guten morgen",
    "guten tag",
    "guten abend",
    "guten mittag",
    "gute morgen",
    "gute tag",
    "hallo",
    "hi",
    "hey",
    "servus",
    "grüß gott",
    "gruss gott",
    "good morning",
    "good afternoon",
    "good evening",
    "hello",
    "ciao",
    "moin",
)

NEWS_GENERIC_KEYWORDS: Set[str] = {
    "news",
    "nachrichten",
    "schlagzeilen",
    "aktuell",
    "neueste",
    "neuesten",
    "latest",
    "headlines",
    "headline",
    "today",
    "heute",
}

COUNTRY_ENGLISH_NAMES: Dict[str, str] = {
    "AT": "Austria",
    "DE": "Germany",
    "US": "United States",
    "GB": "United Kingdom",
    "RO": "Romania",
    "CH": "Switzerland",
    "FR": "France",
    "IT": "Italy",
    "ES": "Spain",
    "NL": "Netherlands",
}

_GREETING_REGEX = r"^(?:\s*(?:" + "|".join(re.escape(p) for p in GREETING_PREFIXES) + r")\b[\s,!.:-]*)+(?:ki[_\-\s]?ana\b[\s,!.:-]*)?"
_GREETING_PATTERN = re.compile(_GREETING_REGEX, re.IGNORECASE)


def has_explicit_web_override(query: str) -> bool:
    if not query:
        return False
    lowered = query.lower()
    return any(pattern in lowered for pattern in EXPLICIT_WEB_OVERRIDE_PATTERNS)


def is_news_query(query: str) -> bool:
    if not query:
        return False
    lowered = query.lower()
    if any(keyword in lowered for keyword in NEWS_KEYWORDS):
        return True
    if "heute" in lowered and any(
        hint in lowered for hints in COUNTRY_HINTS.values() for hint in hints
    ):
        return True
    return False


def infer_country_from_query(query: str) -> Optional[str]:
    if not query:
        return None
    lowered = query.lower()
    for country, hints in COUNTRY_HINTS.items():
        if any(hint in lowered for hint in hints):
            return country
    return None


def infer_country(user_locale: Optional[str], query: str) -> Optional[str]:
    explicit = infer_country_from_query(query)
    if explicit:
        return explicit

    if user_locale:
        loc = user_locale.lower()
        if loc in LANG_TO_DEFAULT_COUNTRY:
            return LANG_TO_DEFAULT_COUNTRY[loc]
        lang = loc.split("-", 1)[0]
        if lang in LANG_TO_DEFAULT_COUNTRY:
            return LANG_TO_DEFAULT_COUNTRY[lang]

    return None


def build_news_search_queries(
    user_query: str,
    locale_hint: Optional[str] = None,
    country_code: Optional[str] = None,
) -> List[str]:
    """Generate normalized search queries for news intents."""

    if not user_query:
        return []

    original = user_query.strip()
    if not original:
        return []

    cleaned = _GREETING_PATTERN.sub("", original).lstrip(" ,;:!?.-_").strip()
    if not cleaned:
        cleaned = original

    lowered = original.lower()
    normalized_lower = cleaned.lower()

    detected_country = None
    if "österreich" in lowered or "austria" in lowered:
        detected_country = "AT"
    elif country_code:
        detected_country = str(country_code).upper()

    has_news_keyword = any(keyword in normalized_lower for keyword in NEWS_GENERIC_KEYWORDS)

    def _country_names(code: str) -> Tuple[str, str]:
        native = COUNTRY_LABELS.get(code.upper(), code.upper())
        english = COUNTRY_ENGLISH_NAMES.get(code.upper(), native)
        return native, english

    locale_lower = (locale_hint or "").lower()
    prefer_german = locale_lower.startswith("de") or (detected_country in {"AT", "DE", "CH"})

    queries: List[str] = []
    if has_news_keyword:
        if detected_country:
            native_name, english_name = _country_names(detected_country)
            german_templates = [
                f"{native_name} aktuelle Nachrichten",
                f"{native_name} Schlagzeilen heute",
            ]
            english_templates = [
                f"{english_name} latest news",
                f"{english_name} headlines today",
            ]
            if prefer_german:
                queries.extend(german_templates + english_templates)
            else:
                queries.extend(english_templates + german_templates)
        else:
            queries.extend(
                [
                    cleaned,
                    f"{cleaned} latest news",
                    f"{cleaned} headlines today",
                ]
            )
    else:
        queries.append(cleaned)

    if cleaned not in queries:
        queries.append(cleaned)

    unique: List[str] = []
    seen: Set[str] = set()
    for candidate in queries:
        candidate_norm = (candidate or "").strip()
        if not candidate_norm:
            continue
        key = candidate_norm.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate_norm)

    return unique or [original]


def classify_source_risk(trust_score: float) -> str:
    if trust_score >= 0.8:
        return "high_trust"
    if trust_score >= 0.5:
        return "medium_trust"
    return "low_trust"


def boost_local_news_results(results: List[Dict[str, Any]], prefs: NewsSourcePrefs) -> List[Dict[str, Any]]:
    if not results:
        return results

    preferred = [domain.lower() for domain in (prefs.primary_sources or []) if domain]

    def _score(item: Dict[str, Any]) -> float:
        trust = float(item.get("trust_score") or 0.5)
        score = trust * 10.0
        url = (item.get("url") or "").lower()
        matched = False
        if preferred:
            for idx, domain in enumerate(preferred):
                if domain in url:
                    matched = True
                    score += 5.0
                    score += max(0.0, (len(preferred) - idx)) * 0.5
                    break
            if not matched:
                score -= 2.5
        return score

    return sorted(results, key=_score, reverse=True)


def maybe_seed_news_crawler(country: Optional[str]) -> None:
    """Hook for future crawler integration (no-op for now)."""
    return None


def _resolve_country_label(country_code: Optional[str]) -> str:
    if not country_code:
        return "Global"
    normalized = str(country_code).upper()
    return COUNTRY_LABELS.get(normalized, normalized)


def _preferred_timezone(country_code: Optional[str]) -> str:
    if not country_code:
        return DEFAULT_TIMEZONE
    normalized = str(country_code).upper()
    return COUNTRY_TIMEZONES.get(normalized, DEFAULT_TIMEZONE)


def _build_time_metadata(country_code: Optional[str]) -> Dict[str, str]:
    now_utc = datetime.now(ZoneInfo("UTC"))
    tz_name = _preferred_timezone(country_code)
    try:
        target_tz = ZoneInfo(tz_name)
    except Exception:
        target_tz = ZoneInfo(DEFAULT_TIMEZONE)
        tz_name = DEFAULT_TIMEZONE

    local_dt = now_utc.astimezone(target_tz)
    utc_iso = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    local_iso = local_dt.replace(microsecond=0).isoformat()
    local_display = local_dt.strftime("%d.%m.%Y %H:%M %Z")
    return {
        "timestamp_utc_iso": utc_iso,
        "timestamp_local_iso": local_iso,
        "timestamp_local_display": local_display,
        "timezone": tz_name,
    }


def _domain_from_url(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(str(url))
        host = parsed.netloc or ""
        return host.lower()
    except Exception:
        return ""


def _build_highlights(snippets: List[WebSnippet], limit: int = 4) -> List[Dict[str, Any]]:
    highlights: List[Dict[str, Any]] = []
    if not snippets:
        return highlights

    for snippet in snippets[: max(1, limit)]:
        summary_text = snippet.summary or snippet.raw_excerpt or snippet.snippet or ""
        summary_clean = " ".join(summary_text.split())
        highlights.append(
            {
                "title": snippet.title,
                "url": snippet.url,
                "domain": _domain_from_url(snippet.url),
                "summary": summary_clean,
                "trust_score": snippet.trust_score,
            }
        )

    return highlights

EXPLICIT_PHRASES = [
    "suche im internet",
    "websuche",
    "web suche",
    "schau im internet",
    "schau im web",
    "im web",
    "online finden",
    "recherche im internet",
    "nutze das internet",
    "googeln",
    "google",
    "aktuellen preis",
    "aktueller preis",
    "aktuellen kurs",
    "breaking news",
    "neuesten informationen",
    "latest news",
    "look up online",
    "check the web",
    "news über",
]

TIME_SENSITIVE_TERMS = [
    "heute",
    "gestern",
    "morgen",
    "aktuell",
    "aktuelle",
    "aktuellen",
    "aktuelles",
    "jetzt",
    "momentan",
    "gerade",
    "live",
    "laufend",
    "neuest",
    "neueste",
    "neuesten",
    "update",
    "updates",
    "preis",
    "preise",
    "kurs",
    "kurse",
    "börse",
    "börsenkurs",
    "wechselkurs",
    "inflation",
    "wetter",
    "verkehr",
    "statistik",
    "zahlen",
    "tabelle",
    "ergebnis",
    "score",
    "spielstand",
    "realtime",

]
def _extract_locale_value(user_locale: Optional[Any]) -> Optional[str]:
    if not user_locale:
        return None
    if isinstance(user_locale, dict):
        for key in ("value", "locale", "language", "lang"):
            val = user_locale.get(key)
            if val:
                return str(val)
        return None
    return str(user_locale)


def _extract_country_code_from_locale(user_locale: Optional[Any]) -> Optional[str]:
    if not user_locale:
        return None
    if isinstance(user_locale, dict):
        for key in ("country_code", "country", "iso_country"):
            val = user_locale.get(key)
            if val:
                code = str(val).strip()
                return code.upper() if code else None
        locale_val = _extract_locale_value(user_locale)
    else:
        locale_val = str(user_locale)

    if not locale_val:
        return None

    normalized = str(locale_val).replace("_", "-")
    parts = [p for p in normalized.split("-") if p]
    if len(parts) >= 2:
        candidate = parts[-1]
        if len(candidate) == 2:
            return candidate.upper()
    if len(normalized) == 2:
        return normalized.upper()
    return None

ALWAYS_FALSE_ENV = {"0", "false", "off", "no"}
ALWAYS_TRUE_ENV = {"1", "true", "on", "yes"}


def _cfg(name: str, default: Optional[str] = None) -> Optional[str]:
    """Config lookup: settings.<NAME> > env > default."""
    if settings is not None and hasattr(settings, name):
        try:
            value = getattr(settings, name)
            if isinstance(value, str) and value.strip():
                return value
        except Exception:
            pass
    env_val = os.getenv(name)
    if env_val is not None and str(env_val).strip():
        return str(env_val)
    return default


def _allow_net() -> bool:
    allow = _cfg("ALLOW_NET", "1")
    return str(allow or "1").strip().lower() not in ALWAYS_FALSE_ENV


def _normalize_lang(lang: Optional[str]) -> str:
    if not lang:
        return "de"
    lowered = str(lang).strip().lower()
    if lowered.startswith("en"):
        return "en"
    if lowered.startswith("de"):
        return "de"
    return lowered[:2] or "de"


def should_use_web(
    user_message: str,
    lang: Optional[str] = None,
    *,
    user_locale: Optional[str] = None,
    force_fresh: bool = False,
) -> bool:
    """Heuristic check whether a prompt should trigger web search."""
    if not user_message:
        return False

    if force_fresh:
        return True

    forced = (_cfg("KIANA_WEB_FORCE", "") or "").strip().lower()
    if forced in ALWAYS_TRUE_ENV:
        return True
    if forced in ALWAYS_FALSE_ENV:
        return False

    query = (user_message or "").strip()
    if not query:
        return False

    if has_explicit_web_override(query):
        return True

    normalized = query.lower()

    if is_news_query(normalized):
        return True

    for phrase in EXPLICIT_PHRASES:
        if phrase in normalized:
            return True

    for term in TIME_SENSITIVE_TERMS:
        if term in normalized:
            return True

    if "web" in normalized and ("such" in normalized or "find" in normalized):
        return True

    if "internet" in normalized and any(
        tok in normalized for tok in ["such", "find", "recherch", "check"]
    ):
        return True

    # Time-/year-based stats: 2023+ with "statistik"/"zahlen"/"news"/"aktuell"
    year_match = re.search(r"\b20(2[3-9]|3[0-9])\b", normalized)
    if year_match and any(
        term in normalized
        for term in ["statistik", "zahlen", "report", "bericht", "news", "aktuell"]
    ):
        return True

    return False


@dataclass
class WebSnippet:
    title: str
    url: str
    summary: str
    raw_excerpt: str
    snippet: str = ""
    score: Optional[float] = None
    trust_score: Optional[float] = None
    risk: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WebEnricher:
    """Web enrichment helper that performs search, fetch and summarisation."""

    def __init__(
        self,
        search_endpoint: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        snapshot_root: Optional[str] = None,
        http_client: Optional[Callable[..., Any]] = None,
        enable_snapshots: Optional[bool] = None,
    ) -> None:
        if BeautifulSoup is None:
            raise RuntimeError("WebEnricher requires beautifulsoup4 (bs4)")
        # Search endpoint: Env > argument > default
        endpoint_cfg = search_endpoint or _cfg("KIANA_WEB_SEARCH_ENDPOINT", "") or None
        self.search_endpoint: Optional[str] = (endpoint_cfg or "").strip() or None

        # Timeout robust parsen
        try:
            env_timeout = _cfg("KIANA_WEB_TIMEOUT", str(timeout)) or str(timeout)
            self.timeout: float = float(env_timeout)
        except (TypeError, ValueError):
            self.timeout = DEFAULT_TIMEOUT

        # Snapshot-Config: Env + optional override
        snapshot_cfg_raw = str(_cfg("KIANA_WEB_SNAPSHOT", "1") or "1").strip().lower()
        env_enable = snapshot_cfg_raw not in ALWAYS_FALSE_ENV
        self.snapshot_enabled: bool = (
            env_enable if enable_snapshots is None else bool(enable_snapshots)
        )
        self.snapshot_root: str = (
            snapshot_root
            or _cfg("KIANA_WEB_SNAPSHOT_ROOT", DEFAULT_SNAPSHOT_ROOT)
            or DEFAULT_SNAPSHOT_ROOT
        )

        self.max_pages: int = DEFAULT_MAX_PAGES
        self.max_chars: int = DEFAULT_MAX_CHARS

        # HTTP-Client vorbereiten (für Tests mockbar)
        self._session = httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True)
        self.http_client = http_client or self._default_http_client
        # Für Alt-Code, der evtl. self.session nutzt:
        self.session = self._session  # type: ignore[attr-defined]

        # Snapshot-/Memory-Integration
        self.snapshot_tags = ["web_snapshot", "web"]
        self.store_callable = (
            getattr(memory_adapter, "store", None) if memory_adapter else None
        )

        provider_cfg = _cfg(
            "WEB_SEARCH_PROVIDER_ORDER",
            "serper-news,serper,duckduckgo-json,duckduckgo-html,brave-news,serpapi-news,newsapi-org,google",
        ) or ""
        self.provider_order: List[str] = [
            segment.strip().lower()
            for segment in provider_cfg.split(",")
            if segment.strip()
        ] or ["duckduckgo-json", "duckduckgo-html"]

        active_provider_cfg = str(_cfg("KIANA_WEB_SEARCH_PROVIDER", "") or "").strip().lower()
        if active_provider_cfg:
            if active_provider_cfg in self.provider_order:
                self.provider_order = [active_provider_cfg] + [
                    p for p in self.provider_order if p != active_provider_cfg
                ]
            else:
                self.provider_order = [active_provider_cfg] + list(self.provider_order)

        self.active_provider: Optional[str] = (
            active_provider_cfg or (self.provider_order[0] if self.provider_order else None)
        )
        self._last_provider: Optional[str] = None

        news_enabled_raw = str(_cfg("NEWS_LAYER_ENABLED", "1") or "1").strip().lower()
        news_enabled = news_enabled_raw not in ALWAYS_FALSE_ENV
        news_max_articles = _cfg("NEWS_LAYER_MAX_ARTICLES", "6") or "6"
        self.news_layer: Optional[GlobalNewsLayerType] = None
        if news_enabled and GlobalNewsLayer is not None:
            try:
                self.news_layer = GlobalNewsLayer(
                    enabled=True,
                    max_articles=int(news_max_articles),
                )
            except Exception:  # pragma: no cover - fallback to disabled layer
                self.news_layer = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def web_search(
        self,
        query: str,
        *,
        lang: Optional[str] = None,
        max_results: int = 3,
        country_code: Optional[str] = None,
        prefer_news_provider: bool = False,
        source_prefs: Optional[Dict[str, Any]] = None,
        mode: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        lang_norm = _normalize_lang(lang)
        country_norm = (str(country_code or "AT") or "AT").strip().upper()[:2] or "AT"
        if not _allow_net():
            logger.info("Web search skipped: network not allowed")
            return []
        if not query.strip():
            return []

        self._last_provider = None
        logger.info(
            "web_enricher.provider_order: %s",
            ",".join(self.provider_order) or "<empty>",
        )
        effective_order = list(self.provider_order or [])
        if prefer_news_provider:
            pinned = "serper-news"
            if pinned in effective_order:
                effective_order = [pinned] + [p for p in effective_order if p != pinned]
            else:
                effective_order = [pinned] + effective_order
        logger.info(
            "web_enricher.provider_order_effective: %s",
            ",".join(effective_order) or "<empty>",
        )
        provider_handlers = {
            "serper-news": lambda: self._search_serper_news(
                query,
                lang_norm,
                max_results,
                country_code=country_norm,
            ),
            "serper": lambda: self._search_serper(query, lang_norm, max_results),
            "duckduckgo-json": lambda: self._search_via_endpoint(query, lang_norm, max_results),
            "duckduckgo-html": lambda: self._search_duckduckgo_html(query, lang_norm, max_results),
            "brave-news": lambda: self._search_brave_news(query, lang_norm, max_results),
            "serpapi-news": lambda: self._search_serpapi_news(query, lang_norm, max_results),
            "newsapi-org": lambda: self._search_newsapi_org(query, lang_norm, max_results),
            "google": lambda: self._search_google_cse(query, max_results),
        }

        tried_any_provider = False
        last_error: Optional[str] = None

        for provider_name in effective_order:
            handler = provider_handlers.get(provider_name)
            if handler is None:
                logger.warning(
                    "web_enricher: unknown provider configured: %s",
                    provider_name,
                )
                continue
            tried_any_provider = True
            logger.info(
                "web_enricher.provider_invoke: provider=%s query=%r",
                provider_name,
                query,
            )
            try:
                batch = handler()
                raw_count = len(batch) if batch else 0
                logger.info(
                    "web_enricher.provider_raw_count: provider=%s raw_count=%d query=%r",
                    provider_name,
                    raw_count,
                    query,
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                last_error = str(exc)
                logger.warning(
                    "web_enricher.provider_fail: provider=%s error=%s query=%r",
                    provider_name,
                    exc,
                    query,
                )
                continue
            annotated = self._annotate_results(batch, provider_name)
            if provider_name == "serper-news" and annotated and not source_prefs and not prefer_news_provider:
                annotated = self._downrank_homepages(annotated)

            ranked = self._apply_source_prefs_ranking(
                annotated,
                source_prefs=source_prefs,
                mode=(mode or ("news" if prefer_news_provider else "")),
            )
            annotated = ranked
            annotated_count = len(annotated) if annotated else 0
            logger.info(
                "web_enricher.provider_annotated_count: provider=%s annotated_count=%d query=%r",
                provider_name,
                annotated_count,
                query,
            )
            if raw_count > 0 and annotated_count == 0:
                logger.warning(
                    "web_enricher: results disappeared after annotation: provider=%s raw=%d annotated=%d query=%r",
                    provider_name,
                    raw_count,
                    annotated_count,
                    query,
                )
            if annotated:
                self._last_provider = provider_name
                logger.info(
                    "web_enricher.provider_success: provider=%s results=%d query=%r",
                    provider_name,
                    len(annotated),
                    query,
                )
                return annotated

        # Fallback provider (only if not already tried explicitly)
        if "duckduckgo-html" not in self.provider_order:
            try:
                provider_name = "duckduckgo-html"
                logger.info(
                    "web_enricher.provider_invoke: provider=%s query=%r",
                    provider_name,
                    query,
                )
                fallback = self._search_duckduckgo_html(query, lang_norm, max_results)
                raw_count = len(fallback) if fallback else 0
                logger.info(
                    "web_enricher.provider_raw_count: provider=%s raw_count=%d query=%r",
                    provider_name,
                    raw_count,
                    query,
                )
                annotated = self._annotate_results(fallback, provider_name)
                logger.info(
                    "web_enricher.provider_annotated_count: provider=%s annotated_count=%d query=%r",
                    provider_name,
                    len(annotated),
                    query,
                )
                if annotated:
                    self._last_provider = provider_name
                    logger.info(
                        "web_enricher.provider_success: provider=%s results=%d query=%r",
                        provider_name,
                        len(annotated),
                        query,
                    )
                    return annotated
            except Exception as exc:  # pragma: no cover
                last_error = str(exc)
                logger.warning(
                    "web_enricher.provider_fail: provider=%s error=%s query=%r",
                    "duckduckgo-html",
                    exc,
                    query,
                )

        if not tried_any_provider:
            logger.warning(
                "web_enricher.provider_fail: provider=all error=%s query=%r",
                "no providers configured",
                query,
            )
            return []

        logger.info(
            "web_enricher.provider_fail: provider=all error=%s query=%r",
            "no providers returned results" + (f" (last_error={last_error})" if last_error else ""),
            query,
        )
        return []

    def _apply_source_prefs_ranking(
        self,
        results: List[Dict[str, Any]],
        *,
        source_prefs: Optional[Dict[str, Any]],
        mode: Optional[str],
    ) -> List[Dict[str, Any]]:
        if not results:
            return []

        mode_norm = str(mode or "").strip().lower()
        if mode_norm not in {"news", "current", "current_events"} and not source_prefs:
            return results

        preferred: List[str] = []
        blocked: List[str] = []
        if isinstance(source_prefs, dict):
            preferred = list(source_prefs.get("preferred_sources") or source_prefs.get("preferred") or [])
            blocked = list(source_prefs.get("blocked_sources") or source_prefs.get("blocked") or [])
            # Some call sites pass full block; support nested meta
            meta = source_prefs.get("meta") if isinstance(source_prefs.get("meta"), dict) else None
            if meta:
                preferred = list(meta.get("preferred_sources") or preferred)
                blocked = list(meta.get("blocked_sources") or blocked)
        preferred_set = {str(x).strip().lower() for x in preferred if str(x).strip()}
        blocked_set = {str(x).strip().lower() for x in blocked if str(x).strip()}

        preferred_hits = 0
        blocked_hits = 0
        homepages = 0

        def is_homepage(url: str) -> bool:
            try:
                parsed = urlparse(url)
                path = parsed.path or ""
            except Exception:
                path = ""
            if not path or path == "/":
                return True
            segments = [seg for seg in path.split("/") if seg]
            return len(segments) <= 1

        scored: List[Tuple[Tuple[int, int], Dict[str, Any]]] = []
        for idx, item in enumerate(results):
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            score = 0
            domain = ""
            try:
                domain = (urlparse(url).netloc or "").lower()
                if domain.startswith("www."):
                    domain = domain[4:]
            except Exception:
                domain = ""

            if domain and domain in preferred_set:
                score += 30
                preferred_hits += 1
            if domain and domain in blocked_set:
                score -= 100
                blocked_hits += 1
            if url and is_homepage(url):
                score -= 20
                homepages += 1

            entry = dict(item)
            entry["_prefs_score"] = score
            scored.append(((-score, idx), entry))

        scored.sort(key=lambda pair: pair[0])
        ordered = [item for _, item in scored]

        top_domains: List[str] = []
        for item in ordered[:6]:
            try:
                dom = (urlparse(str(item.get("url") or "")).netloc or "").lower()
                if dom.startswith("www."):
                    dom = dom[4:]
                if dom and dom not in top_domains:
                    top_domains.append(dom)
            except Exception:
                continue

        logger.info(
            "web_enricher.ranking: preferred_hits=%d blocked_hits=%d homepages=%d top_domains=%s",
            preferred_hits,
            blocked_hits,
            homepages,
            top_domains,
        )
        return ordered

    def fetch_and_summarize_pages(
        self,
        query: str,
        results: List[Dict[str, Any]],
        *,
        lang: Optional[str] = None,
        max_pages: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> List[WebSnippet]:
        if not results:
            return []

        lang_norm = _normalize_lang(lang)
        limit_pages = max_pages or self.max_pages
        max_len = max_chars or self.max_chars
        snippets: List[WebSnippet] = []

        for item in results[:limit_pages]:
            url = item.get("url") or ""
            title = item.get("title") or "Web"
            if not url or not url.startswith("http"):
                continue

            html = self._fetch_url(url)
            if not html:
                continue

            paragraphs = self._extract_paragraphs(html)
            if not paragraphs:
                continue

            summary = self._summarize_paragraphs(
                paragraphs, query=query, lang=lang_norm, max_chars=max_len
            )
            raw_excerpt = self._build_excerpt(paragraphs, max_chars=max_len)
            snippet = item.get("snippet") or self._shorten(raw_excerpt, 320)

            snippets.append(
                WebSnippet(
                    title=str(title),
                    url=str(url),
                    summary=summary,
                    raw_excerpt=raw_excerpt,
                    snippet=snippet,
                    score=item.get("score"),
                    trust_score=item.get("trust_score"),
                    risk=item.get("risk"),
                )
            )

        return snippets

    def build_web_context(
        self,
        user_message: str,
        *,
        lang: Optional[str] = None,
        max_results: int = 3,
        max_pages: Optional[int] = None,
        user_locale: Optional[Any] = None,
        force_fresh: bool = False,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context_payload = user_context or {}
        user_ctx_locale = None
        if isinstance(context_payload, dict):
            user_ctx_locale = context_payload.get("user_locale")
        locale_value = _extract_locale_value(user_ctx_locale or user_locale)

        lang_candidate = context_payload.get("lang") if isinstance(context_payload, dict) else None
        lang_norm = _normalize_lang(lang_candidate or locale_value or lang)

        flag_payload = context_payload.get("pipeline_flags") if isinstance(context_payload, dict) else None
        if isinstance(flag_payload, dict):
            if flag_payload.get("needs_current") or flag_payload.get("force_fresh"):
                force_fresh = True
        context_country = context_payload.get("country_code") if isinstance(context_payload, dict) else None
        user_country_code = None
        if context_country:
            user_country_code = str(context_country).upper()
        else:
            inferred_country = _extract_country_code_from_locale(user_ctx_locale or user_locale)
            user_country_code = inferred_country.upper() if inferred_country else None
        country_code = (user_country_code or "AT").strip().upper()[:2] or "AT"
        query = (user_message or "").strip()
        provider_meta: Dict[str, Any] = {
            "active_provider": self.active_provider,
            "provider_order": list(self.provider_order or []),
        }
        logger.info(
            "web_enricher.build_web_context: user_query=%r force_fresh=%s user_context=%s",
            query,
            force_fresh,
            context_payload,
        )
        summary_base: Dict[str, Any] = {
            "query": query,
            "num_results": 0,
            "sources": [],
        }

        if not should_use_web(
            user_message,
            lang_norm,
            user_locale=locale_value,
            force_fresh=force_fresh,
        ):
            logger.debug("web_enricher: web not applicable for prompt")
            payload = dict(summary_base)
            payload["reason"] = "not_applicable"
            return {
                "used": False,
                "reason": "not_applicable",
                "query": query,
                "summary": payload,
                **provider_meta,
            }

        if not _allow_net():
            logger.info("web_enricher: network disabled, skipping web step")
            payload = dict(summary_base)
            payload["reason"] = "network_disabled"
            return {
                "used": False,
                "reason": "network_disabled",
                "query": query,
                "summary": payload,
                **provider_meta,
            }

        original_query = query
        news_intent = is_news_query(original_query)
        context_news_country = None
        if isinstance(context_payload, dict):
            context_news_country = context_payload.get("news_country_hint")
        target_country_for_queries = None
        if context_news_country:
            target_country_for_queries = str(context_news_country).upper()
        elif user_country_code:
            target_country_for_queries = user_country_code

        news_queries: List[str] = []
        if news_intent:
            news_queries = build_news_search_queries(
                original_query,
                locale_hint=locale_value,
                country_code=target_country_for_queries,
            )
        if not news_queries:
            news_queries = [original_query]
        logger.info(
            "web_enricher.news_queries: base=%r queries=%r country_hint=%s",
            original_query,
            news_queries,
            context_payload.get("news_country_hint") if isinstance(context_payload, dict) else None,
        )

        tried_queries: List[str] = []
        search_results: List[Dict[str, Any]] = []
        effective_query = news_queries[0]

        # Phase 2 (Codex): for news we need a broader candidate set for relevance + dedup.
        search_max_results = int(max_results)
        try:
            if news_intent or force_fresh:
                search_max_results = max(search_max_results, 12)
        except Exception:
            search_max_results = int(max_results)

        source_prefs = None
        trust_profile = None
        interest_profile = None
        trust_mode = "news" if (news_intent or force_fresh) else "search"
        try:
            if isinstance(context_payload, dict):
                uid = context_payload.get("user_id")
            else:
                uid = None
            needs_prefs = bool(news_intent or force_fresh or (context_payload.get("pipeline_flags") or {}).get("needs_current")) if isinstance(context_payload, dict) else bool(news_intent or force_fresh)
            if uid is not None and needs_prefs:
                try:
                    from netapi.core import addressbook
                    from netapi import memory_store

                    bid = addressbook.get_source_prefs(
                        user_id=int(uid),
                        country=country_code,
                        lang=lang_norm,
                        intent="news",
                    )
                    blk = memory_store.get_block(bid) if bid else None
                    if isinstance(blk, dict):
                        source_prefs = blk.get("meta") or blk
                except Exception:
                    source_prefs = None

            if uid is not None:
                try:
                    from netapi.core import addressbook
                    from netapi import memory_store

                    bid2 = addressbook.get_source_trust_profile(
                        user_id=int(uid),
                        country=country_code,
                        mode=trust_mode,
                    )
                    blk2 = memory_store.get_block(bid2) if bid2 else None
                    if isinstance(blk2, dict):
                        trust_profile = blk2.get("meta") or blk2
                    else:
                        trust_profile = None
                except Exception:
                    trust_profile = None

            if uid is not None:
                try:
                    from netapi.core import addressbook
                    from netapi import memory_store

                    bid3 = addressbook.get_interest_profile(
                        user_id=int(uid),
                        country=country_code,
                        lang=lang_norm,
                        mode=trust_mode,
                    )
                    blk3 = memory_store.get_block(bid3) if bid3 else None
                    if isinstance(blk3, dict):
                        interest_profile = blk3.get("meta") or blk3
                    else:
                        interest_profile = None
                except Exception:
                    interest_profile = None
        except Exception:
            source_prefs = None
            trust_profile = None
            interest_profile = None

        for candidate in news_queries:
            candidate_clean = (candidate or "").strip()
            if not candidate_clean:
                continue
            if candidate_clean in tried_queries:
                continue
            tried_queries.append(candidate_clean)
            prefer_news_provider = bool(
                force_fresh
                or news_intent
                or (context_payload.get("needs_current") if isinstance(context_payload, dict) else False)
                or (context_payload.get("is_news") if isinstance(context_payload, dict) else False)
            )
            batch = self.web_search(
                candidate_clean,
                lang=lang_norm,
                max_results=search_max_results,
                country_code=country_code,
                prefer_news_provider=prefer_news_provider,
                source_prefs=source_prefs,
                mode=("news" if prefer_news_provider else None),
            )
            provider_label = self._last_provider or "unknown"
            logger.info(
                "web_enricher.search_result: provider=%s query=%r num_results=%d",
                provider_label,
                candidate_clean,
                len(batch or []),
            )
            if batch:
                search_results = batch
                effective_query = candidate_clean
                break

        if news_intent and not search_results:
            fallback_queries: List[str] = []
            if target_country_for_queries:
                english_name = COUNTRY_ENGLISH_NAMES.get(
                    target_country_for_queries.upper(),
                    target_country_for_queries.upper(),
                )
                fallback_queries.extend([
                    f"{english_name} latest news",
                    f"{english_name} headlines today",
                ])
            fallback_queries.append("world latest news")
            for candidate in fallback_queries:
                candidate_clean = (candidate or "").strip()
                if not candidate_clean or candidate_clean in tried_queries:
                    continue
                tried_queries.append(candidate_clean)
                batch = self.web_search(
                    candidate_clean,
                    lang=lang_norm,
                    max_results=search_max_results,
                    country_code=country_code,
                    prefer_news_provider=True,
                    source_prefs=source_prefs,
                    mode="news",
                )
                provider_label = self._last_provider or "unknown"
                logger.info(
                    "web_enricher.search_result: provider=%s query=%r num_results=%d",
                    provider_label,
                    candidate_clean,
                    len(batch or []),
                )
                if batch:
                    search_results = batch
                    effective_query = candidate_clean
                    break

        summary_base["query"] = effective_query
        summary_base["original_query"] = original_query
        if news_intent:
            summary_base["tried_queries"] = list(tried_queries)

        if not search_results:
            logger.info("web_enricher: no search results for query '%s'", original_query)
            payload = dict(summary_base)
            if news_intent:
                payload["reason"] = "no_results_after_fallback"
            else:
                payload["reason"] = "no_results"
            return {
                "used": False,
                "reason": payload.get("reason"),
                "query": original_query,
                "summary": payload,
                **provider_meta,
            }

        search_query = effective_query

        ranked_results: List[Dict[str, Any]] = list(search_results or [])

        # --- PR3: Trust weighting + diversity + exploration (reorder-only)
        prefs_used = False
        try:
            if isinstance(source_prefs, dict):
                preferred = list(source_prefs.get("preferred_sources") or source_prefs.get("preferred") or [])
                blocked = list(source_prefs.get("blocked_sources") or source_prefs.get("blocked") or [])
                prefs_used = bool(preferred or blocked or (source_prefs.get("notes") or "").strip())
        except Exception:
            prefs_used = False

        diversity_applied = False
        exploration_used = False
        explored_domain = None

        try:
            from netapi.core import source_trust as _st  # local import to avoid hard dependency cycles

            # Ensure trust profile exists (block-based, no DB)
            try:
                if trust_profile is None and uid is not None:
                    from netapi.core import addressbook
                    from netapi import memory_store

                    profile = _st.empty_profile(user_id=int(uid), country=country_code, mode=trust_mode)
                    title = f"Source Trust: user={int(uid)} {country_code} {trust_mode}"
                    content = json.dumps(profile, ensure_ascii=False, indent=2)
                    tags = [
                        "source_trust_profile",
                        "trust:sources",
                        f"user:{int(uid)}",
                        f"country:{country_code}",
                        f"mode:{trust_mode}",
                    ]
                    bid = memory_store.add_block(title=title, content=content, tags=tags, meta=profile)
                    addressbook.index_source_trust_profile(
                        block_id=bid,
                        user_id=int(uid),
                        country=country_code,
                        mode=trust_mode,
                        domain_count=0,
                        updated_at=profile.get("updated_at"),
                    )
                    trust_profile = profile
            except Exception:
                pass

            # Apply per-user trust weighting
            trust_weighted = _st.apply_trust_weight_reorder(search_results, trust_profile=trust_profile)
            diverse, diversity_applied = _st.apply_diversity_reorder(
                trust_weighted,
                top_n=_st.TOP_N,
                max_per_domain=_st.MAX_PER_DOMAIN_TOP_N,
            )
            rng = random.Random()
            explored, exploration_used, explored_domain = _st.apply_explore_reintroduce(
                diverse,
                trust_profile=trust_profile,
                rng=rng,
                top_n=_st.TOP_N,
                last_slots=_st.EXPLORE_LAST_SLOTS,
                chance=_st.EXPLORE_CHANCE,
                weight_threshold=_st.EXPLORE_WEIGHT_THRESHOLD,
                max_per_domain=_st.MAX_PER_DOMAIN_TOP_N,
            )
            search_results = explored

            ranked_results = list(search_results or [])

            # Track exposure (seen) for top domains (block-based)
            try:
                if uid is not None and trust_profile is not None:
                    shown = _st.unique_domains_from_results(search_results, limit=_st.TOP_N)
                    if shown:
                        _st.bump_seen(trust_profile, shown)
                        from netapi.core import addressbook
                        from netapi import memory_store

                        title = f"Source Trust: user={int(uid)} {country_code} {trust_mode}"
                        content = json.dumps(trust_profile, ensure_ascii=False, indent=2)
                        tags = [
                            "source_trust_profile",
                            "trust:sources",
                            f"user:{int(uid)}",
                            f"country:{country_code}",
                            f"mode:{trust_mode}",
                        ]
                        bid3 = memory_store.add_block(title=title, content=content, tags=tags, meta=trust_profile)
                        addressbook.index_source_trust_profile(
                            block_id=bid3,
                            user_id=int(uid),
                            country=country_code,
                            mode=trust_mode,
                            domain_count=len((trust_profile.get("domain_stats") or {}) if isinstance(trust_profile.get("domain_stats"), dict) else {}),
                            updated_at=trust_profile.get("updated_at"),
                        )
            except Exception:
                pass
        except Exception:
            # PR3 post-ranking is best-effort; never fail web enrichment.
            diversity_applied = False
            exploration_used = False
            explored_domain = None

        # --- Phase 2 (Codex): Relevance + dedup/cluster (reorder-only)
        relevance_applied = False
        dedup_applied = False
        penalty_applied = False
        service_penalty_applied = False
        penalized_examples: List[Dict[str, str]] = []
        interest_used = False
        filtered_out_count = 0
        top_categories: List[str] = []
        try:
            if news_intent or force_fresh or trust_mode == "news":
                from netapi.core import news_relevance as _rel

                rel_ranked, rel_meta = _rel.apply_relevance_reorder(
                    list(search_results or []),
                    query=search_query,
                    top_n_considered=10,
                )
                search_results = rel_ranked
                relevance_applied = True
                filtered_out_count = int(rel_meta.filtered_out_count)
                top_categories = list(rel_meta.top_categories or [])

                deduped, dedup_applied = _rel.apply_title_dedup_reorder(
                    list(search_results or []),
                    top_n=10,
                )
                search_results = deduped

                penalized, svc_meta = _rel.apply_service_penalty_reorder(
                    list(search_results or []),
                    query=search_query,
                    top_n_considered=10,
                )
                search_results = penalized
                service_penalty_applied = bool(svc_meta.applied)
                penalized_examples = list(svc_meta.penalized_examples or [])
                # Keep legacy flag for backward compatibility.
                penalty_applied = bool(service_penalty_applied)

                # Phase 4: interest-driven reorder (reorder-only) if we have a profile.
                interest_ranked, interest_used, top_cats2 = _rel.apply_interest_reorder(
                    list(search_results or []),
                    profile=interest_profile if isinstance(interest_profile, dict) else None,
                    top_n_considered=10,
                )
                if bool(interest_used):
                    search_results = interest_ranked
                    if top_cats2:
                        top_categories = list(top_cats2)

                ranked_results = list(search_results or [])
        except Exception:
            relevance_applied = False
            dedup_applied = False
            penalty_applied = False
            service_penalty_applied = False
            penalized_examples = []
            interest_used = False
            filtered_out_count = 0
            top_categories = []

        country_hint = infer_country(locale_value, query)
        inferred_country_code = country_hint.upper() if country_hint else None
        context_news_code = (
            str(context_news_country).upper()
            if context_news_country
            else None
        )
        news_country_code = context_news_code or inferred_country_code or user_country_code
        news_prefs = get_news_sources_for_locale(news_country_code)
        focus_country_code = news_prefs.country or news_country_code
        active_country_hint = None
        if focus_country_code:
            active_country_hint = focus_country_code.lower()
        elif country_hint:
            active_country_hint = country_hint.lower()

        if news_intent or force_fresh:
            maybe_seed_news_crawler(active_country_hint)

        ranked_sources: List[NewsSourceType] = []
        news_source_map: Dict[str, NewsSourceType] = {}
        if (news_intent or force_fresh) and focus_country_code:
            ranked_sources = _fetch_ranked_news_sources(
                focus_country_code,
                locale_value,
                tags=["NEWS"],
                limit=25,
            )
        elif news_intent:
            ranked_sources = _fetch_ranked_news_sources(
                user_country_code,
                locale_value,
                tags=["NEWS"],
                limit=25,
            )
        if ranked_sources:
            news_source_map = {src.domain.lower(): src for src in ranked_sources if src and src.domain}

        enriched_results: List[Dict[str, Any]] = []
        for item in search_results:
            url = item.get("url")
            trust_score = get_trust_score_from_url(url) if url else 0.5
            risk = classify_source_risk(trust_score)
            entry = {**item, "trust_score": trust_score, "risk": risk}
            domain = _domain_from_url(url)
            if news_source_map and domain in news_source_map:
                src = news_source_map[domain]
                entry["news_source"] = {
                    "domain": src.domain,
                    "trust_score": src.trust_score,
                    "is_preferred": src.is_preferred,
                    "country_code": src.country_code,
                    "locale": src.locale,
                    "last_seen_at": src.last_seen_at.isoformat() if src.last_seen_at else None,
                }
            enriched_results.append(entry)

        enriched_results = boost_local_news_results(enriched_results, news_prefs)
        if news_source_map:
            enriched_results = _prioritize_with_news_sources(
                enriched_results,
                news_map=news_source_map,
                user_country=focus_country_code or user_country_code,
                user_locale=locale_value,
            )

        snippets = self.fetch_and_summarize_pages(
            search_query,
            enriched_results,
            lang=lang_norm,
            max_pages=max_pages,
        )
        if not snippets:
            logger.warning("web_enricher: failed to summarise search results")
            payload = dict(summary_base)
            payload["reason"] = "summaries_failed"
            return {
                "used": False,
                "reason": "summaries_failed",
                "query": query,
                "summary": payload,
            }

        result_lookup = {
            entry.get("url"): entry for entry in enriched_results if entry.get("url")
        }
        serialized_snippets: List[Dict[str, Any]] = []
        for snippet in snippets:
            payload = snippet.to_dict()
            meta = result_lookup.get(payload.get("url"))
            if isinstance(meta, dict):
                if meta.get("provider"):
                    payload["provider"] = meta.get("provider")
                if meta.get("source"):
                    payload["source"] = meta.get("source")
                if meta.get("news_source"):
                    payload["news_source"] = meta.get("news_source")
                if meta.get("published"):
                    payload["published"] = meta.get("published")
            serialized_snippets.append(payload)

        # Phase 2: Build lightweight source cards for news output/UI from ranked results.
        news_cards: List[Dict[str, Any]] = []
        try:
            if news_intent or force_fresh or trust_mode == "news":
                from netapi.core import news_relevance as _rel

                news_cards = _rel.build_news_cards_from_results(enriched_results, limit=7)
        except Exception:
            news_cards = []

        top_domains: List[str] = []
        try:
            for item in (search_results or [])[:12]:
                dom = _domain_from_url(item.get("url"))
                if dom and dom not in top_domains:
                    top_domains.append(dom)
                if len(top_domains) >= 3:
                    break
        except Exception:
            top_domains = []

        generated_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        context: Dict[str, Any] = {
            "used": True,
            "query": search_query,
            "original_query": original_query,
            "lang": lang_norm,
            "generated_at": generated_at,
            "snippets": serialized_snippets,
            "news_cards": news_cards,
            "ranked_results": ranked_results,
            "provider": self._last_provider or self.active_provider or "unknown",
            "mode": trust_mode,
            "country": country_code,
            "prefs_used": bool(prefs_used),
            "diversity_applied": bool(diversity_applied),
            "exploration_used": bool(exploration_used),
            "relevance_applied": bool(relevance_applied),
            "dedup_applied": bool(dedup_applied),
            "penalty_applied": bool(penalty_applied),
            "service_penalty_applied": bool(service_penalty_applied),
            "penalized_examples": list(penalized_examples or []),
            "interest_used": bool(interest_used),
            "filtered_out_count": int(filtered_out_count),
            "top_categories": list(top_categories or []),
            "top_domains": top_domains,
            "explored_domain": explored_domain,
            **provider_meta,
        }
        if news_intent:
            context["tried_queries"] = list(tried_queries)

        trust_breakdown: Dict[str, int] = {
            "high_trust": 0,
            "medium_trust": 0,
            "low_trust": 0,
        }
        trust_scores: List[float] = []
        for snippet in snippets:
            score = float(snippet.trust_score or 0.0)
            trust_scores.append(score)
            risk_key = snippet.risk or classify_source_risk(score)
            trust_breakdown[risk_key] = trust_breakdown.get(risk_key, 0) + 1

        summary_sources: List[Dict[str, Any]] = []
        aggregated_domains: List[str] = []
        for snippet in snippets[:5]:
            domain = _domain_from_url(snippet.url)
            if domain and domain not in aggregated_domains:
                aggregated_domains.append(domain)
            news_meta = None
            if domain and news_source_map and domain in news_source_map:
                src = news_source_map[domain]
                news_meta = {
                    "domain": src.domain,
                    "trust_score": src.trust_score,
                    "is_preferred": src.is_preferred,
                    "country_code": src.country_code,
                    "locale": src.locale,
                }
            source_entry: Dict[str, Any] = {
                "title": snippet.title,
                "url": snippet.url,
                "domain": domain,
                "snippet": snippet.snippet or snippet.summary,
                "snippet_trust_score": snippet.trust_score,
                "trust_score": snippet.trust_score,
                "risk": snippet.risk,
            }
            if news_meta:
                source_entry["news_source"] = news_meta
                if news_meta.get("country_code"):
                    source_entry["country_code"] = news_meta.get("country_code")
                if news_meta.get("is_preferred") is not None:
                    source_entry["is_preferred"] = bool(news_meta.get("is_preferred"))
                if news_meta.get("trust_score") is not None:
                    source_entry["trust_score"] = news_meta.get("trust_score")
            summary_sources.append(source_entry)

        # Phase 2: For news, use ranked search results for 5–7 bullets even if only a few pages were fetched.
        if news_intent or force_fresh or trust_mode == "news":
            highlights: List[Dict[str, Any]] = []
            for card in (news_cards or [])[:7]:
                summary_text = ""
                try:
                    # Try to pick the snippet text from the enriched result (if present)
                    summary_text = str(card.get("summary") or "")
                except Exception:
                    summary_text = ""
                if not summary_text:
                    # Card builder stores no summary; fall back to empty.
                    summary_text = ""
                highlights.append(
                    {
                        "title": card.get("title"),
                        "url": card.get("url"),
                        "domain": card.get("domain"),
                        "summary": summary_text,
                        "source": card.get("label"),
                        "published": card.get("date") or card.get("published"),
                        "category": card.get("category"),
                        "relevance": card.get("relevance"),
                    }
                )
        else:
            highlights = _build_highlights(snippets, limit=5)
        time_info = _build_time_metadata(focus_country_code)

        summary_payload: Dict[str, Any] = {
            "query": search_query,
            "original_query": original_query,
            "num_results": len(snippets),
            "sources": summary_sources,
            "trust_breakdown": trust_breakdown,
            "source_domains": aggregated_domains,
            "highlights": highlights,
            "news_cards": news_cards,
            "relevance_applied": bool(relevance_applied),
            "filtered_out_count": int(filtered_out_count),
            "top_categories": list(top_categories or []),
            "timestamp_utc_iso": time_info["timestamp_utc_iso"],
            "timestamp_local_iso": time_info["timestamp_local_iso"],
            "timestamp_local_display": time_info["timestamp_local_display"],
            "timezone": time_info["timezone"],
            "country_focus": focus_country_code,
            "country_label": _resolve_country_label(focus_country_code),
            "news_intent": bool(news_intent),
            "force_fresh": bool(force_fresh),
        }
        if news_intent:
            summary_payload["tried_queries"] = list(tried_queries)
            summary_payload["search_query"] = search_query
        if ranked_sources:
            summary_payload["news_source_candidates"] = [
                {
                    "domain": src.domain,
                    "trust_score": src.trust_score,
                    "is_preferred": src.is_preferred,
                    "country_code": src.country_code,
                    "locale": src.locale,
                }
                for src in ranked_sources[:12]
            ]
        if trust_scores:
            summary_payload["average_trust_score"] = round(sum(trust_scores) / len(trust_scores), 3)
        if user_country_code and user_country_code != (focus_country_code or ""):
            summary_payload["user_country"] = user_country_code
        if news_prefs.country:
            summary_payload["news_country"] = news_prefs.country
        if focus_country_code:
            summary_payload["country"] = focus_country_code.lower()
        if news_prefs.primary_sources:
            summary_payload["news_primary_sources"] = news_prefs.primary_sources
        if news_prefs.fallback_sources:
            summary_payload["news_fallback_sources"] = news_prefs.fallback_sources

        context["summary"] = summary_payload

        if self.news_layer and (news_intent or force_fresh):
            try:
                news_context = self.news_layer.build_from_snippets(
                    query=search_query,
                    original_query=original_query,
                    snippets=serialized_snippets,
                    focus_country=focus_country_code or user_country_code,
                    locale=locale_value,
                    providers_used=[self._last_provider] if self._last_provider else None,
                )
            except Exception:  # pragma: no cover - ensure web context still returns
                news_context = None
            if news_context:
                context["news_context"] = news_context
                summary_payload["news_layer"] = {
                    "article_count": news_context.get("article_count"),
                    "providers": news_context.get("providers"),
                }

        snapshot_path = self._store_snapshot_if_configured(context)
        if snapshot_path:
            context["snapshot_path"] = snapshot_path

        logger.debug(
            "web_enricher: built context with %d snippets (snapshot=%s)",
            len(snippets),
            bool(snapshot_path),
        )
        return context

    # ------------------------------------------------------------------
    # Internal helpers (override in tests as needed)
    # ------------------------------------------------------------------
    def _default_http_client(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return self._session.get(url, params=params, timeout=timeout or self.timeout, **kwargs)

    @staticmethod
    def _annotate_results(
        results: Optional[List[Dict[str, Any]]],
        provider_name: str,
    ) -> List[Dict[str, Any]]:
        if not results:
            return []
        annotated: List[Dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            entry.setdefault("provider", provider_name)
            entry.setdefault("source", entry.get("provider"))
            annotated.append(entry)
        return annotated

    def _downrank_homepages(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not items:
            return []

        scored: List[Tuple[Tuple[int, float, int], Dict[str, Any]]] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            title = str(item.get("title") or "")
            snippet = str(item.get("snippet") or "")
            has_date = bool(item.get("date") or item.get("published"))

            penalty = 0
            try:
                parsed = urlparse(url)
                path = parsed.path or ""
            except Exception:
                path = ""

            if not path or path == "/":
                penalty += 6
            else:
                segments = [seg for seg in path.split("/") if seg]
                if len(segments) <= 1:
                    penalty += 3
                if not any(ch.isdigit() for ch in path) and not any(
                    token in path.lower()
                    for token in (
                        "article",
                        "news",
                        "story",
                        "stories",
                        "politics",
                        "world",
                        "economy",
                        "business",
                        "sport",
                        "culture",
                    )
                ):
                    penalty += 1

            if not has_date:
                penalty += 1

            quality = 0.0
            if has_date:
                quality += 2.0
            quality += min(len(snippet), 240) / 120.0
            quality += min(len(title), 140) / 140.0

            scored.append(((penalty, -quality, idx), item))

        scored.sort(key=lambda pair: pair[0])
        return [item for _, item in scored]

    def _search_via_endpoint(
        self, query: str, lang: str, max_results: int
    ) -> List[Dict[str, Any]]:
        endpoint = (self.search_endpoint or DEFAULT_SEARCH_ENDPOINT).strip()
        url = endpoint
        params: Optional[Dict[str, Any]] = None

        if "{query}" in endpoint:
            url = endpoint.format(query=quote_plus(query))
        else:
            params = {
                "q": query,
                "format": "json",
                "no_redirect": 1,
                "no_html": 1,
                "t": "ki_ana",
            }
            if lang == "de":
                params["kl"] = "de-de"
            elif lang == "en":
                params["kl"] = "us-en"

        resp = self.http_client(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return self._parse_duckduckgo_json(data, max_results)

    def _parse_duckduckgo_json(self, data: Any, max_results: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        def add_result(
            title: str, url: str, snippet: str, score: Optional[float] = None
        ) -> None:
            if not url or not url.startswith("http"):
                return
            results.append(
                {
                    "title": title or "Web",
                    "url": url,
                    "snippet": snippet,
                    "score": score,
                }
            )
        if not isinstance(data, dict):
            return results

        # Primary results
        primary_results = data.get("Results")
        if isinstance(primary_results, list):
            for item in primary_results:
                if not isinstance(item, dict):
                    continue
                add_result(
                    str(item.get("Text") or item.get("Title") or "Web"),
                    str(item.get("FirstURL") or item.get("URL") or ""),
                    str(item.get("Text") or item.get("Description") or ""),
                )
                if len(results) >= max_results:
                    return results[:max_results]

        # Related topics
        related_topics = data.get("RelatedTopics")
        if isinstance(related_topics, list):
            for topic in related_topics:
                if len(results) >= max_results:
                    break
                if isinstance(topic, dict) and "FirstURL" in topic:
                    add_result(
                        str(topic.get("Text") or topic.get("Name") or "Web"),
                        str(topic.get("FirstURL") or ""),
                        str(topic.get("Text") or ""),
                    )
                elif isinstance(topic, dict) and isinstance(topic.get("Topics"), list):
                    for sub in topic.get("Topics") or []:
                        if len(results) >= max_results:
                            break
                        if not isinstance(sub, dict):
                            continue
                        add_result(
                            str(sub.get("Text") or sub.get("Name") or "Web"),
                            str(sub.get("FirstURL") or ""),
                            str(sub.get("Text") or ""),
                        )

        # Abstract as fallback
        abstract_url = data.get("AbstractURL")
        if len(results) < max_results and abstract_url:
            add_result(
                str(data.get("Heading") or "Web"),
                str(abstract_url),
                str(data.get("AbstractText") or data.get("Abstract") or ""),
            )

        return results[:max_results]

    def _search_duckduckgo_html(
        self, query: str, lang: str, max_results: int
    ) -> List[Dict[str, Any]]:
        try:
            params = {"q": query, "kl": "de-de" if lang == "de" else "us-en"}
            resp = self.http_client(
                "https://duckduckgo.com/html/",
                params=params,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            results: List[Dict[str, Any]] = []
            for result in soup.select("div.result"):
                link = result.select_one("a.result__a")
                if not link:
                    continue
                url = link.get("href") or ""
                if not url.startswith("http"):
                    continue
                title = link.get_text(" ", strip=True) or "Web"
                snippet_tag = (
                    result.select_one("a.result__snippet")
                    or result.select_one("div.result__snippet")
                )
                snippet = (
                    snippet_tag.get_text(" ", strip=True) if snippet_tag else ""
                )
                results.append({"title": title, "url": url, "snippet": snippet})
                if len(results) >= max_results:
                    break
            return results
        except Exception as exc:  # pragma: no cover - network edge cases
            logger.warning("DuckDuckGo search failed: %s", exc)
            return []

    # Backwards compatibility for tests overriding _search_duckduckgo
    def _search_duckduckgo(
        self, query: str, lang: str, max_results: int
    ) -> List[Dict[str, Any]]:
        return self._search_duckduckgo_html(query, lang, max_results)

    def _search_brave_news(
        self,
        query: str,
        lang: str,
        max_results: int,
    ) -> List[Dict[str, Any]]:
        api_key = _cfg("BRAVE_SEARCH_API_KEY")
        if not api_key:
            return []
        params: Dict[str, Any] = {
            "q": query,
            "count": max_results,
            "freshness": "ps",
        }
        region = self._region_from_lang(lang)
        if region:
            params["country"] = region.upper()
        headers = {
            "X-Subscription-Token": api_key,
            "Accept": "application/json",
        }
        resp = self.http_client(
            "https://api.search.brave.com/res/v1/news/search",
            params=params,
            timeout=self.timeout,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        articles = data.get("results") or data.get("articles") or []
        parsed: List[Dict[str, Any]] = []
        for item in articles:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or item.get("link")
            if not url or not str(url).startswith("http"):
                continue
            source_meta = item.get("source")
            if isinstance(source_meta, dict):
                source_label = source_meta.get("name")
            else:
                source_label = source_meta
            parsed.append(
                {
                    "title": item.get("title") or item.get("name") or "News",
                    "url": url,
                    "snippet": item.get("description") or item.get("snippet") or "",
                    "published": item.get("published") or item.get("date"),
                    "source": source_label,
                }
            )
            if len(parsed) >= max_results:
                break
        return parsed

    def _search_serper(
        self,
        query: str,
        lang: str,
        max_results: int,
    ) -> List[Dict[str, Any]]:
        def _run() -> List[Dict[str, Any]]:
            return asyncio.run(search_serper(query, lang, max_results))

        try:
            if not _cfg("SERPER_API_KEY"):
                logger.warning("serper: SERPER_API_KEY missing – cannot perform web search")
                return []

            result_holder: Dict[str, Any] = {}
            error_holder: Dict[str, BaseException] = {}

            def runner() -> None:
                try:
                    result_holder["value"] = _run()
                except BaseException as exc:  # pragma: no cover - defensive
                    error_holder["error"] = exc

            thread = threading.Thread(target=runner, name="serper-async-bridge", daemon=True)
            thread.start()
            thread.join(timeout=max(self.timeout * 2, 30.0))

            if thread.is_alive():
                logger.error("serper(sync-bridge): timed out waiting for async Serper call")
                return []

            if "error" in error_holder:
                raise error_holder["error"]

            results = result_holder.get("value")
            if not isinstance(results, list):
                return []
            return results
        except Exception as exc:
            logger.error(
                "serper(sync-bridge): ERROR for query=%r: %s",
                query,
                exc,
                exc_info=True,
            )
            return []

    def _search_serper_news(
        self,
        query: str,
        lang: str,
        max_results: int,
        *,
        country_code: str,
    ) -> List[Dict[str, Any]]:
        api_key = _cfg("SERPER_API_KEY")
        if not api_key:
            logger.warning("serper-news: SERPER_API_KEY missing – cannot perform news search")
            return []

        endpoint = os.getenv("SERPER_NEWS_API_ENDPOINT", "https://google.serper.dev/news")
        hl = (str(lang or "en").strip().lower().split("-")[0] or "en")
        if len(hl) != 2:
            hl = "en"
        gl = (str(country_code or "AT").strip().lower()[:2] or "at")
        payload: Dict[str, Any] = {
            "q": query,
            "num": int(max_results),
            "hl": hl,
            "gl": gl,
        }
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        }

        logger.info(
            "serper-news.request: q=%r hl=%s gl=%s num=%s endpoint=%s",
            query,
            hl,
            gl,
            int(max_results),
            endpoint,
        )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code >= 400:
                logger.error(
                    "serper-news.http_error: status=%s body=%s",
                    resp.status_code,
                    (resp.text or "")[:2000],
                )
                return []
            data = resp.json() or {}
        except Exception as exc:
            logger.error(
                "serper-news: ERROR for query=%r: %s",
                query,
                exc,
                exc_info=True,
            )
            return []

        try:
            results = _parse_serper_news_results(data)
        except Exception as exc:
            logger.error(
                "serper-news: parse error for query=%r: %s",
                query,
                exc,
                exc_info=True,
            )
            return []

        return results

    def _search_google_cse(
        self,
        query: str,
        max_results: int,
    ) -> List[Dict[str, Any]]:
        # Google Custom Search (CSE) – allgemeine Websuche
        # Nutzt GOOGLE_API_KEY und GOOGLE_CSE_ID aus der Umgebung.
    
        api_key = _cfg("GOOGLE_API_KEY")
        cse_id = _cfg("GOOGLE_CSE_ID")

        if not api_key or not cse_id:
            return []

        params = {
            "key": api_key,
            "cx": cse_id,
            "q": query,
            "num": max_results,
        }

        try:
            resp = self.http_client(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
                timeout=self.cfg.request_timeout_seconds,
            )
        except Exception:
            return []

        data = resp.json() or {}
        items = data.get("items") or []

        results: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            url = item.get("link")
            if not url or not str(url).startswith("http"):
                continue

            title = item.get("title") or item.get("htmlTitle") or url
            snippet = item.get("snippet") or item.get("htmlSnippet") or ""

            results.append(
                {
                    "title": str(title),
                    "url": str(url),
                    "snippet": str(snippet),
                    "source": "google",
                }
            )

        return results


    def _search_serpapi_news(
        self,
        query: str,
        lang: str,
        max_results: int,
    ) -> List[Dict[str, Any]]:
        api_key = _cfg("SERPAPI_API_KEY")
        if not api_key:
            return []
        params = {
            "engine": "google_news",
            "q": query,
            "api_key": api_key,
            "gl": self._region_from_lang(lang) or "us",
            "hl": "de" if lang == "de" else "en",
            "num": max_results,
        }
        resp = self.http_client(
            "https://serpapi.com/search",
            params=params,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        articles = data.get("news_results") or []
        parsed: List[Dict[str, Any]] = []
        for item in articles:
            if not isinstance(item, dict):
                continue
            url = item.get("link") or item.get("url")
            if not url or not str(url).startswith("http"):
                continue
            parsed.append(
                {
                    "title": item.get("title") or "News",
                    "url": url,
                    "snippet": item.get("snippet") or item.get("description") or "",
                    "published": item.get("date") or item.get("published"),
                    "source": item.get("source") or item.get("publisher"),
                }
            )
            if len(parsed) >= max_results:
                break
        return parsed

    def _search_newsapi_org(
        self,
        query: str,
        lang: str,
        max_results: int,
    ) -> List[Dict[str, Any]]:
        api_key = _cfg("NEWSAPI_API_KEY")
        if not api_key:
            return []
        params = {
            "apiKey": api_key,
            "q": query,
            "pageSize": max_results,
            "language": "de" if lang == "de" else "en",
            "sortBy": "publishedAt",
        }
        resp = self.http_client(
            "https://newsapi.org/v2/everything",
            params=params,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        articles = data.get("articles") or []
        parsed: List[Dict[str, Any]] = []
        for item in articles:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not url or not str(url).startswith("http"):
                continue
            parsed.append(
                {
                    "title": item.get("title") or "News",
                    "url": url,
                    "snippet": item.get("description") or item.get("content") or "",
                    "published": item.get("publishedAt"),
                    "source": (item.get("source") or {}).get("name") if isinstance(item.get("source"), dict) else item.get("source"),
                }
            )
            if len(parsed) >= max_results:
                break
        return parsed

    @staticmethod
    def _region_from_lang(lang: str) -> Optional[str]:
        lowered = (lang or "").lower()
        if lowered.startswith("de"):
            return "at"
        if lowered.startswith("en"):
            return "us"
        return None

    def _fetch_url(self, url: str) -> Optional[str]:
        try:
            resp = self.http_client(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except Exception:
            logger.debug("web_enricher: failed to fetch %s", url)
            return None

    def _extract_paragraphs(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        for bad in soup(
            ["script", "style", "noscript", "header", "footer", "nav", "form", "aside"]
        ):
            bad.decompose()
        paragraphs: List[str] = []
        for el in soup.find_all(["p", "li", "article", "section"]):
            text = el.get_text(" ", strip=True)
            if len(text) >= 60:
                cleaned = re.sub(r"\s+", " ", text).strip()
                if cleaned and cleaned not in paragraphs:
                    paragraphs.append(cleaned)
        return paragraphs

    def _summarize_paragraphs(
        self,
        paragraphs: List[str],
        *,
        query: str,
        lang: str,
        max_chars: int,
    ) -> str:
        terms = [tok for tok in re.split(r"\W+", query.lower()) if tok]
        scored = sorted(
            (
                (paragraph, self._score_paragraph(paragraph, terms))
                for paragraph in paragraphs
            ),
            key=lambda item: item[1],
            reverse=True,
        )

        collected: List[str] = []
        total = 0
        for paragraph, _ in scored:
            if total + len(paragraph) > max_chars:
                space_left = max_chars - total
                if space_left > 120:
                    truncated = paragraph[:space_left].rsplit(" ", 1)[0] + " …"
                    collected.append(truncated)
                break
            collected.append(paragraph)
            total += len(paragraph)
            if total >= max_chars:
                break

        sentences: List[str] = []
        for paragraph in collected:
            sentences.extend(self._sentence_split(paragraph))

        bullets = [s for s in sentences if len(s) > 30][:5]
        if not bullets:
            bullets = collected[:3]

        prefix = "Wesentliches:" if lang == "de" else "Key points:"
        bullet_prefix = "• "
        summary_body = prefix + "\n" + "\n".join(bullet_prefix + b for b in bullets)
        tldr_intro = "Kurz gesagt:" if lang == "de" else "TL;DR:"
        tldr_line = (
            bullets[0] if bullets else (collected[0] if collected else "Keine Daten gefunden.")
        )
        return summary_body + "\n\n" + tldr_intro + " " + tldr_line

    def _build_excerpt(self, paragraphs: List[str], max_chars: int) -> str:
        excerpt_parts: List[str] = []
        total = 0
        for paragraph in paragraphs:
            if len(paragraph) < 40:
                continue
            excerpt_parts.append(paragraph)
            total += len(paragraph)
            if total >= max_chars:
                break
        excerpt = "\n\n".join(excerpt_parts)
        if len(excerpt) > max_chars:
            excerpt = excerpt[: max_chars - 3].rstrip() + "..."
        return excerpt

    @staticmethod
    def _score_paragraph(paragraph: str, terms: List[str]) -> float:
        lowered = paragraph.lower()
        hits = sum(1 for term in terms if term and term in lowered)
        return hits * 3 + min(len(paragraph) / 300.0, 1.5)

    @staticmethod
    def _sentence_split(text: str) -> List[str]:
        parts = re.split(r"(?<=[.!?…])\s+", text)
        return [segment.strip() for segment in parts if len(segment.strip()) > 0]

    @staticmethod
    def _shorten(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."

    def _store_snapshot_if_configured(
        self, context: Dict[str, Any]
    ) -> Optional[str]:
        if not self.snapshot_enabled or not self.store_callable:
            return None

        try:
            snippets = context.get("snippets") or []
            if not snippets:
                return None

            title = f"Web Snapshot: {context.get('query', '')[:72]}"
            timestamp = int(time.time())
            parts: List[str] = []

            for snippet in snippets[:3]:
                parts.append(
                    "# {title}\n{summary}\nQuelle: {url}\n".format(
                        title=snippet.get("title") or "Web",
                        summary=snippet.get("summary")
                        or snippet.get("raw_excerpt")
                        or "",
                        url=snippet.get("url") or "",
                    )
                )

            body = "\n\n".join(parts)
            meta = {
                "query": context.get("query"),
                "generated_at": context.get("generated_at"),
                "timestamp": timestamp,
                "snippets": len(snippets),
                "tags": self.snapshot_tags,
            }

            path = self.store_callable(
                title=title,
                content=body,
                tags=self.snapshot_tags,
                url=None,
                meta=meta,
                root=self.snapshot_root,
            )
            return str(path)
        except Exception as exc:  # pragma: no cover
            logger.debug("web_enricher: snapshot storage failed: %s", exc)
            return None


__all__ = [
    "WebEnricher",
    "WebSnippet",
    "should_use_web",
    "build_news_search_queries",
]