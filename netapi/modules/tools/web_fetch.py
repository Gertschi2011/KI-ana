from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 KI_ana/1.0 +https://ki-ana.at/"
    )
}
DEFAULT_TIMEOUT = 12


def _allow_net() -> bool:
    return str(os.getenv("ALLOW_NET", "1")).strip() == "1"


def _cse_cfg() -> tuple[Optional[str], Optional[str]]:
    key = os.getenv("GOOGLE_CSE_API_KEY")
    cx = os.getenv("GOOGLE_CSE_CX")
    key = (str(key).strip() if key else None)
    cx = (str(cx).strip() if cx else None)
    return key or None, cx or None


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def web_search(query: str, *, lang: str = "de", max_results: int = 5) -> List[Dict[str, str]]:
    """Return list of {url,title} for a query.

    Prefers Google CSE when configured; otherwise uses DuckDuckGo HTML.
    Wikipedia is intentionally NOT used as a fallback.
    """
    if not _allow_net():
        return []
    q = (query or "").strip()
    if not q:
        return []

    key, cx = _cse_cfg()
    if key and cx:
        try:
            params: Dict[str, Any] = {"key": key, "cx": cx, "q": q, "num": int(max_results)}
            if str(lang).lower().startswith("de"):
                params["lr"] = "lang_de"
                params["hl"] = "de"
            elif str(lang).lower().startswith("en"):
                params["lr"] = "lang_en"
                params["hl"] = "en"
            r = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
                headers=HEADERS,
                timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json() or {}
            out: List[Dict[str, str]] = []
            for it in (data.get("items") or [])[: int(max_results)]:
                url = (it.get("link") or it.get("formattedUrl") or "").strip()
                title = (it.get("title") or it.get("htmlTitle") or "Web").strip()
                if url.startswith("http"):
                    out.append({"url": url, "title": _clean_text(title)})
            return out
        except Exception:
            # Fall through to DDG
            pass

    try:
        url = "https://duckduckgo.com/html/"
        params = {"q": q, "kl": "de-de" if str(lang).lower().startswith("de") else "us-en"}
        r = requests.get(url, params=params, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        out: List[Dict[str, str]] = []
        for a in soup.select("a.result__a"):
            href = (a.get("href") or "").strip()
            title = a.get_text(" ", strip=True)
            if href.startswith("http"):
                out.append({"url": href, "title": _clean_text(title)})
            if len(out) >= int(max_results):
                break
        return out
    except Exception:
        return []


def web_open(url: str, *, timeout_s: int = DEFAULT_TIMEOUT, max_chars: int = 12000) -> Tuple[str, str]:
    """Fetch a URL and return (title, cleaned_text)."""
    if not _allow_net():
        return "", ""
    u = (url or "").strip()
    if not (u.startswith("http://") or u.startswith("https://")):
        return "", ""
    try:
        r = requests.get(u, headers=HEADERS, timeout=int(timeout_s))
        r.raise_for_status()
        html = r.text or ""
        soup = BeautifulSoup(html, "html.parser")
        for bad in soup(["script", "style", "noscript", "header", "footer", "nav", "form", "aside"]):
            bad.extract()
        title = ""
        try:
            if soup.title and soup.title.get_text():
                title = _clean_text(soup.title.get_text(" ", strip=True))
        except Exception:
            title = ""
        parts: List[str] = []
        for el in soup.find_all(["p", "li", "article", "section"]):
            t = _clean_text(el.get_text(" ", strip=True))
            if len(t) >= 60:
                parts.append(t)
        text = "\n".join(parts)
        text = text[: int(max_chars)]
        return title, text
    except Exception:
        return "", ""


def _score_paragraph(p: str, terms: List[str]) -> float:
    pl = p.lower()
    hits = sum(1 for t in terms if t and t in pl)
    return hits * 3.0 + min(len(p) / 400.0, 2.0)


def web_search_and_summarize(
    query: str,
    *,
    lang: str = "de",
    max_results: int = 3,
    max_chars: int = 900,
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """Search and summarize top pages.

    Returns (text, sources). Sources are stable dicts: {title,url,kind:"web",origin:"web"}.
    """
    q = (query or "").strip()
    if not q or not _allow_net():
        return None, []

    hits = web_search(q, lang=lang, max_results=max_results)
    if not hits:
        return None, []

    terms = [t for t in re.split(r"\W+", q.lower()) if t]
    paras_scored: List[Tuple[str, float]] = []
    sources: List[Dict[str, Any]] = []

    for h in hits[: int(max_results)]:
        url = (h.get("url") or "").strip()
        if not url:
            continue
        title, text = web_open(url)
        if not title:
            title = (h.get("title") or "Web").strip()
        sources.append({"title": title or "Web", "url": url, "kind": "web", "origin": "web"})
        if text:
            for para in [p.strip() for p in text.split("\n") if len(p.strip()) >= 60]:
                paras_scored.append((para, _score_paragraph(para, terms)))

    if not paras_scored:
        return None, sources

    paras_scored.sort(key=lambda x: -x[1])
    picked: List[str] = []
    total = 0
    for para, _ in paras_scored[:12]:
        if total + len(para) > int(max_chars):
            space = max(0, int(max_chars) - total)
            if space > 120:
                para = para[:space].rsplit(" ", 1)[0] + " …"
                picked.append(para)
            break
        picked.append(para)
        total += len(para) + 1

    text_out = "\n\n".join(picked).strip()
    return (text_out or None), sources
