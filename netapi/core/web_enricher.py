from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

try:  # Settings integration (env over config)
    from netapi.config import settings  # type: ignore
except Exception:  # pragma: no cover
    settings = None  # type: ignore

try:
    from netapi.modules.chat import memory_adapter  # type: ignore
except Exception:  # pragma: no cover
    memory_adapter = None  # type: ignore

logger = logging.getLogger(__name__)

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


def should_use_web(user_message: str, lang: Optional[str] = None) -> bool:
    """Heuristic check whether a prompt should trigger web search."""
    if not user_message:
        return False

    forced = (_cfg("KIANA_WEB_FORCE", "") or "").strip().lower()
    if forced in ALWAYS_TRUE_ENV:
        return True
    if forced in ALWAYS_FALSE_ENV:
        return False

    normalized = (user_message or "").strip().lower()
    if not normalized:
        return False

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
        self._session = requests.Session()
        self._session.headers.update(DEFAULT_HEADERS)
        self.http_client = http_client or self._default_http_client
        # Für Alt-Code, der evtl. self.session nutzt:
        self.session = self._session  # type: ignore[attr-defined]

        # Snapshot-/Memory-Integration
        self.snapshot_tags = ["web_snapshot", "web"]
        self.store_callable = (
            getattr(memory_adapter, "store", None) if memory_adapter else None
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def web_search(
        self,
        query: str,
        *,
        lang: Optional[str] = None,
        max_results: int = 3,
    ) -> List[Dict[str, Any]]:
        lang_norm = _normalize_lang(lang)
        if not _allow_net():
            logger.info("Web search skipped: network not allowed")
            return []
        if not query.strip():
            return []

        # 1) Versuche konfigurierten Endpoint
        try:
            results = self._search_via_endpoint(query, lang_norm, max_results)
            if results:
                logger.debug("web_enricher endpoint results=%d", len(results))
                return results
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("web_enricher endpoint failed: %s", exc)

        # 2) Fallback: DuckDuckGo HTML-Scrape
        results = self._search_duckduckgo_html(query, lang_norm, max_results)
        logger.debug("web_enricher duckduckgo-html results=%d", len(results))
        return results

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
    ) -> Dict[str, Any]:
        lang_norm = _normalize_lang(lang)
        query = (user_message or "").strip()
        summary_base: Dict[str, Any] = {
            "query": query,
            "num_results": 0,
            "sources": [],
        }

        if not should_use_web(user_message, lang_norm):
            logger.debug("web_enricher: web not applicable for prompt")
            payload = dict(summary_base)
            payload["reason"] = "not_applicable"
            return {
                "used": False,
                "reason": "not_applicable",
                "query": query,
                "summary": payload,
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
            }

        search_results = self.web_search(query, lang=lang_norm, max_results=max_results)
        if not search_results:
            logger.info("web_enricher: no search results for query '%s'", query)
            payload = dict(summary_base)
            payload["reason"] = "no_results"
            return {
                "used": False,
                "reason": "no_results",
                "query": query,
                "summary": payload,
            }

        snippets = self.fetch_and_summarize_pages(
            query,
            search_results,
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

        generated_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        context: Dict[str, Any] = {
            "used": True,
            "query": query,
            "lang": lang_norm,
            "generated_at": generated_at,
            "snippets": [snippet.to_dict() for snippet in snippets],
        }
        context["summary"] = {
            "query": query,
            "num_results": len(snippets),
            "sources": [
                {
                    "title": snippet.title,
                    "url": snippet.url,
                    "snippet": snippet.snippet or snippet.summary,
                }
                for snippet in snippets[:5]
            ],
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
    ) -> requests.Response:
        return self._session.get(
            url,
            params=params,
            timeout=timeout or self.timeout,
            **kwargs,
        )

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


__all__ = ["WebEnricher", "WebSnippet", "should_use_web"]