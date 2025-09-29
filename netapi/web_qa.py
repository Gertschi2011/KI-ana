# web_qa.py – Websuche & Zusammenfassung (ohne API-Key)
from __future__ import annotations

import os
import re
import time
import math
from typing import Dict, Any, Optional, List

import requests
from bs4 import BeautifulSoup

# --- Konfiguration -----------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 KianaBot/1.1 "
        "+https://ki-ana.at/"
    )
}
DEFAULT_TIMEOUT = 12

# Wenn du Netz-Zugriff global abschalten möchtest:
#   export ALLOW_NET=0   (oder gar nicht setzen)
#   export ALLOW_NET=1   (aktiv)
# Bevorzugt Settings (aus .env), fällt zurück auf Umgebungsvariable
try:
    from .config import settings as _settings  # type: ignore
except Exception:  # pragma: no cover
    _settings = None  # type: ignore

def _allow_net() -> bool:
    if _settings is not None:
        try:
            return bool(getattr(_settings, "ALLOW_NET", True))
        except Exception:
            pass
    return os.getenv("ALLOW_NET", "1") == "1"

# Google CSE config (optional)
def _cse_cfg() -> tuple[Optional[str], Optional[str]]:
    key = None; cx = None
    if _settings is not None:
        try:
            key = getattr(_settings, "GOOGLE_CSE_API_KEY", None)
        except Exception:
            key = None
        try:
            cx = getattr(_settings, "GOOGLE_CSE_CX", None)
        except Exception:
            cx = None
    key = key or os.getenv("GOOGLE_CSE_API_KEY")
    cx  = cx or os.getenv("GOOGLE_CSE_CX")
    key = (str(key).strip() if key else None)
    cx  = (str(cx).strip() if cx else None)
    return key or None, cx or None


def _yt_key() -> Optional[str]:
    key = None
    if _settings is not None:
        try:
            key = getattr(_settings, "YOUTUBE_API_KEY", None)
        except Exception:
            key = None
    key = key or os.getenv("YOUTUBE_API_KEY")
    return (str(key).strip() if key else None)

# --- Utilities ---------------------------------------------------------------

def _lang_from_context(user_context: Dict[str, Any] | None) -> str:
    lang = (user_context or {}).get("lang") or (user_context or {}).get("locale") or "de"
    lang = str(lang).lower()
    # Normalisieren
    if lang.startswith("de"):  # de, de-AT, de_DE, …
        return "de"
    if lang.startswith("en"):
        return "en"
    return "de"


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _sentence_split(paragraph: str) -> List[str]:
    # sehr einfache Satztrennung
    s = re.split(r"(?<=[.!?…])\s+", paragraph)
    return [t.strip() for t in s if len(t.strip()) > 0]


# --- Suchstrategien ---------------------------------------------------------

def _ddg_search(q: str, lang: str = "de", max_results: int = 3) -> List[Dict[str, str]]:
    """Einfache DuckDuckGo-HTML-Suche. Liefert bis zu max_results Treffer."""
    try:
        url = "https://duckduckgo.com/html/"
        params = {"q": q, "kl": "de-de" if lang == "de" else "us-en"}
        r = requests.get(url, params=params, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        res = []
        for a in soup.select("a.result__a"):
            href = a.get("href")
            title = a.get_text(" ", strip=True)
            if href and href.startswith("http"):
                res.append({"url": href, "title": _clean_text(title)})
            if len(res) >= max_results:
                break
        return res
    except Exception:
        return []


def _google_cse_search(q: str, lang: str = "de", max_results: int = 3) -> List[Dict[str, str]]:
    """Google Custom Search JSON API. Requires GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX.
    Returns list of {url,title}.
    """
    key, cx = _cse_cfg()
    if not key or not cx:
        return []
    try:
        params = {"key": key, "cx": cx, "q": q, "num": max_results}
        # language bias
        if lang == "de":
            params["lr"] = "lang_de"
            params["hl"] = "de"
        elif lang == "en":
            params["lr"] = "lang_en"
            params["hl"] = "en"
        r = requests.get("https://www.googleapis.com/customsearch/v1", params=params, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        items = []
        for it in (data.get("items") or [])[:max_results]:
            link = (it.get("link") or it.get("formattedUrl") or "").strip()
            title = (it.get("title") or it.get("htmlTitle") or "Web").strip()
            if link and link.startswith("http"):
                items.append({"url": link, "title": _clean_text(title)})
        return items
    except Exception:
        return []


def _yt_api_search(q: str, lang: str = "de", max_results: int = 3) -> List[Dict[str, str]]:
    """YouTube Data API search (videos only). Requires YOUTUBE_API_KEY.
    Returns list of {url,title,desc}.
    """
    key = _yt_key()
    if not key:
        return []
    try:
        params = {
            "key": key,
            "part": "snippet",
            "type": "video",
            "maxResults": max_results,
            "q": q,
        }
        if lang == "de":
            params["relevanceLanguage"] = "de"
            params["regionCode"] = "DE"
        r = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        items = []
        for it in (data.get("items") or [])[:max_results]:
            vid = (((it.get("id") or {}).get("videoId")) or "").strip()
            sn  = it.get("snippet") or {}
            title = (sn.get("title") or "YouTube").strip()
            desc  = (sn.get("description") or "").strip()
            if vid:
                items.append({"url": f"https://www.youtube.com/watch?v={vid}", "title": _clean_text(title), "desc": _clean_text(desc)})
        return items
    except Exception:
        return []


def _wiki_opensearch(q: str, lang: str = "de", max_results: int = 2) -> List[Dict[str, str]]:
    base = f"https://{lang}.wikipedia.org/w/api.php"
    try:
        r = requests.get(
            base,
            params={
                "action": "opensearch",
                "format": "json",
                "search": q,
                "limit": max_results,
            },
            headers=HEADERS,
            timeout=DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        out: List[Dict[str, str]] = []
        if isinstance(data, list) and len(data) >= 4:
            titles = data[1] or []
            links = data[3] or []
            for t, u in zip(titles, links):
                if u:
                    out.append({"url": u, "title": t or "Wikipedia"})
        return out
    except Exception:
        return []


# --- Extraktion & Zusammenfassung ------------------------------------------

def _fetch(url: str) -> Optional[str]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def _extract_candidate_paras(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    for bad in soup(["script", "style", "noscript", "header", "footer", "nav", "form", "aside"]):
        bad.extract()
    # paragraph-like Elemente
    texts: List[str] = []
    for el in soup.find_all(["p", "li", "article", "section"]):
        t = el.get_text(" ", strip=True)
        if len(t) >= 60:
            texts.append(_clean_text(t))
    # Duplikate raus
    seen = set()
    uniq = []
    for t in texts:
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)
    return uniq


def _score_paragraph(p: str, q_terms: List[str]) -> float:
    pl = p.lower()
    hits = sum(1 for t in q_terms if t in pl)
    # Länge leicht positiv werten, aber abflachen
    return hits * 3 + min(len(p) / 300.0, 1.5)


def _summarize(paras: List[str], query: str, lang: str = "de", max_chars: int = 800) -> str:
    q_terms = [t for t in re.split(r"\W+", query.lower()) if t]
    scored = sorted(((p, _score_paragraph(p, q_terms)) for p in paras), key=lambda x: -x[1])
    picked: List[str] = []
    total = 0
    for p, _ in scored[:10]:
        if total + len(p) > max_chars:
            # Platz für einen letzten Satz lassen
            space_left = max(0, max_chars - total)
            if space_left > 120:
                p = p[:space_left].rsplit(" ", 1)[0] + " …"
                picked.append(p)
            break
        picked.append(p)
        total += len(p)
        if total >= max_chars:
            break

    # In 3-5 Stichpunkte + kurzer TL;DR umwandeln
    sentences: List[str] = []
    for par in picked:
        sentences.extend(_sentence_split(par))
    bullets = [s for s in sentences if len(s) > 30][:5]
    if not bullets:
        bullets = picked[:3]

    # TL;DR an das Ende
    tldr_intro = "Kurz gesagt:" if lang == "de" else "TL;DR:"
    tldr = bullets[0] if bullets else (picked[0] if picked else "Keine Daten gefunden.")

    if lang == "de":
        prefix = "Wesentliches:"  # angenehm neutral
        bullet_prefix = "• "
    else:
        prefix = "Key points:"
        bullet_prefix = "• "

    body = prefix + "\n" + "\n".join(bullet_prefix + b for b in bullets)
    return body + "\n\n" + tldr_intro + " " + tldr


# --- Öffentliche API --------------------------------------------------------

def web_search_and_summarize(query: str, user_context: Dict[str, Any] | None = None,
                              max_results: int = 3) -> Dict[str, Any]:
    """Führt eine Websuche durch und liefert strukturierte Kurzinfos.

    Rückgabeformat:
    {
      "query": str,
      "allowed": bool,           # ob Netz erlaubt ist
      "results": [               # 0..n Resultate
         {"title": str, "url": str, "summary": str, "source": "web|wiki"}
      ]
    }
    """
    lang = _lang_from_context(user_context)

    if not _allow_net():
        return {"query": query, "allowed": False, "results": []}

    # 1) Suchkandidaten: bevorzugt Google CSE (wenn konfiguriert), plus YouTube (wenn konfiguriert), sonst DuckDuckGo + Wikipedia
    results: List[Dict[str, str]] = []
    cse = _google_cse_search(query, lang=lang, max_results=max_results)
    ddg = [] if cse else _ddg_search(query, lang=lang, max_results=max_results)
    yt  = _yt_api_search(query, lang=lang, max_results=max_results)
    wiki = _wiki_opensearch(query, lang=lang, max_results=2)
    if lang == "de" and not wiki:
        wiki = _wiki_opensearch(query, lang="en", max_results=1)

    # prefer cse results; if absent, take ddg; always include YouTube if present
    candidates = ([("web", x) for x in cse] if cse else [("web", x) for x in ddg]) + [("yt", x) for x in yt] + [("wiki", x) for x in wiki]

    # 2) Für jeden Kandidaten Inhalt holen + zusammenfassen
    out: List[Dict[str, Any]] = []
    for kind, hit in candidates:
        url = hit.get("url")
        title = hit.get("title") or ("Wikipedia" if kind == "wiki" else ("YouTube" if kind == "yt" else "Web"))
        if not url:
            continue
        brief = None
        # For YouTube, use snippet description as quick brief if available
        if kind == "yt" and hit.get("desc"):
            # Wrap description as a couple of points
            desc = hit.get("desc") or ""
            points = [p.strip() for p in desc.split("\n") if p.strip()][:4]
            if points:
                body = ("Wesentliches (Video-Beschreibung):\n" + "\n".join("• " + p[:200] for p in points))
                brief = body + "\n\nKurz gesagt: " + (points[0] if points else desc[:120])
        if not brief:
            html = _fetch(url)
            if not html:
                continue
            paras = _extract_candidate_paras(html)
            if not paras:
                continue
            brief = _summarize(paras, query=query, lang=lang)
        out.append({"title": title, "url": url, "summary": brief, "source": kind})

    return {"query": query, "allowed": True, "results": out}


def web_enrich_and_store(query: str, memory_writer: Optional[Any] = None,
                         user_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Sucht im Web und speichert – falls möglich – die Erkenntnisse als Wissensblock.

    memory_writer: Callable[[str, str, Dict[str, Any]], Any]
       Erwartet Funktion wie: write_block(title: str, content: str, meta: dict)
    """
    result = web_search_and_summarize(query, user_context=user_context)
    if not result.get("allowed"):
        return result

    if memory_writer and result.get("results"):
        # Einen konsolidierten Inhalt bauen
        parts = []
        for r in result["results"][:3]:
            parts.append(f"# {r['title']}\n{r['summary']}\nQuelle: {r['url']}\n")
        content = "\n\n".join(parts)
        meta = {
            "query": query,
            "timestamp": int(time.time()),
            "kind": "web_enrich",
            "num_sources": len(result["results"]),
        }
        try:
            memory_writer(f"Web: {query}", content, meta)
        except Exception:
            # Speicherfehler nicht eskalieren – Suche trotzdem zurückgeben
            pass
    return result
