from __future__ import annotations
import os, json, hashlib, time, re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from html.parser import HTMLParser

KI_ROOT = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
CRAWLED_DIR = KI_ROOT / "memory" / "crawled"
BLOCKS_DIR = KI_ROOT / "memory" / "long_term" / "blocks"
SOURCES_FILE = KI_ROOT / "system" / "crawl_sources.json"
INDEX_FILE = KI_ROOT / "memory" / "index" / "crawled_index.json"
TRUST_INDEX = KI_ROOT / "memory" / "index" / "trust_index.json"
GOALS_PATH = KI_ROOT / "memory" / "index" / "goals.json"

CRAWLED_DIR.mkdir(parents=True, exist_ok=True)
(BLOCKS_DIR).mkdir(parents=True, exist_ok=True)
(INDEX_FILE.parent).mkdir(parents=True, exist_ok=True)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._buf: List[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            d = (data or "").strip()
            if d:
                self._buf.append(d)

    def text(self) -> str:
        t = " ".join(self._buf)
        # normalize whitespace
        t = re.sub(r"\s+", " ", t)
        return t.strip()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _load_sources() -> List[Dict[str, str]]:
    if not SOURCES_FILE.exists():
        return []
    try:
        return json.loads(SOURCES_FILE.read_text(encoding="utf-8")) or []
    except Exception:
        return []


def crawl_html(url: str, timeout: int = 15) -> Tuple[str, str]:
    """Return (text, html)."""
    try:
        req = Request(url, headers={"User-Agent": "KI_anaCrawler/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        p = _TextExtractor()
        p.feed(raw)
        return p.text(), raw
    except (URLError, HTTPError, TimeoutError, Exception):
        return "", ""


def _save_crawled(doc: Dict[str, any]) -> Path:
    h = doc.get("hash") or _sha256((doc.get("url") or "") + (doc.get("text") or ""))
    ts = int(time.time())
    path = CRAWLED_DIR / f"{ts}_{h}.json"
    try:
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return path


def _load_crawled_index() -> Dict[str, Dict[str, any]]:
    if not INDEX_FILE.exists():
        return {}
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _save_crawled_index(idx: Dict[str, Dict[str, any]]) -> None:
    try:
        INDEX_FILE.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def promote_crawled_to_blocks(min_trust: float = 0.5, max_promote: int = 50) -> int:
    """Promote trusted, novel crawled docs to long-term memory blocks.
    Returns number of promotions.
    """
    promoted = 0
    idx = _load_crawled_index()
    for fname in sorted(CRAWLED_DIR.glob("*.json")):
        try:
            data = json.loads(fname.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if float(data.get("score", 0.0)) < float(min_trust):
            continue
        h = data.get("hash")
        if not h or (BLOCKS_DIR / f"{h}.json").exists():
            continue
        block = {
            "id": h,
            "title": data.get("title") or data.get("url") or "(ohne Titel)",
            "content": data.get("text") or "",
            "tags": ["web", "crawl"],
            "url": data.get("url"),
            "source": data.get("source") or "crawl",
            "created": int(time.time())
        }
        try:
            # prefer memory_store if available
            try:
                from .. import memory_store as _mem  # type: ignore
                if hasattr(_mem, "add_block"):
                    _mem.add_block(title=block["title"], content=block["content"], tags=block["tags"], url=block["url"], meta={"id": h, "source": block["source"]})
                    # also dump raw json for traceability
            except Exception:
                pass
            (BLOCKS_DIR / f"{h}.json").write_text(json.dumps(block, ensure_ascii=False, indent=2), encoding="utf-8")
            promoted += 1
        except Exception:
            continue
        if promoted >= max_promote:
            break
    return promoted


def _current_goal_tags() -> List[str]:
    try:
        if not GOALS_PATH.exists():
            return []
        goals = json.loads(GOALS_PATH.read_text(encoding="utf-8"))
        tags: List[str] = []
        if isinstance(goals, list):
            for g in goals:
                for t in (g.get("tags") or []):
                    tt = str(t).lower().strip()
                    if tt:
                        tags.append(tt)
        return sorted(list(set(tags)))
    except Exception:
        return []


def _score_doc(domain: str, text: str, trust_map: Dict[str, float]) -> float:
    base = trust_map.get(domain, trust_map.get("*", 0.5))
    # reward novelty (longer text a bit) and presence of keywords
    bonus = 0.0
    if len(text) > 2000:
        bonus += 0.05
    if any(k in text.lower() for k in ["gesetz", "krieg", "gefahr", "wissenschaft", "forschung", "ethik"]):
        bonus += 0.05
    # learning goals boost
    try:
        for tg in _current_goal_tags():
            if tg and tg in text.lower():
                bonus += 0.08
    except Exception:
        pass
    return max(0.0, min(1.0, base)) + min(0.2, bonus)


def run_crawler_once() -> Dict[str, any]:
    sources = _load_sources()
    if not sources:
        return {"ok": False, "error": "no_sources"}
    trust_map = { (s.get("domain") or s.get("url") or ""): float(s.get("trust", 0.6)) for s in sources }
    idx = _load_crawled_index()
    stats = {"fetched": 0, "saved": 0}
    triggered_topics: List[str] = []
    for s in sources:
        url = s.get("url") or ""
        title = s.get("title") or url
        domain = s.get("domain") or re.sub(r"^https?://([^/]+)/?.*", r"\1", url)
        if not url:
            continue
        text, html = crawl_html(url)
        if not text:
            continue
        h = _sha256(url + "\n" + text[:4096])
        if h in idx:
            continue
        sc = _score_doc(domain, text, trust_map)
        # derive simple tags from title/text for context detection
        low = (title + "\n" + text[:400]).lower()
        tags = []
        for k in ["gesetz", "krieg", "gefahr", "notstand", "krise", "warnung"]:
            if k in low:
                tags.append(k)
        doc = {"url": url, "title": title, "domain": domain, "hash": h, "score": sc, "text": text[:200000], "tags": tags}
        p = _save_crawled(doc)
        idx[h] = {"file": str(p), "url": url, "score": sc}
        stats["fetched"] += 1
        stats["saved"] += 1
        # context change detection (autonomous reaction)
        if detect_critical_context(tags):
            try:
                from . import self_reflection as _sr  # type: ignore
                res = _sr.reflect_context_change(tags=tags, source=url, title=title)  # type: ignore
                if res.get("ok") and res.get("topic"):
                    triggered_topics.append(str(res.get("topic")))
            except Exception:
                pass
    _save_crawled_index(idx)
    out = {"ok": True, **stats}
    if triggered_topics:
        out["context_change"] = sorted(list(set(triggered_topics)))
    return out


def detect_critical_context(tags: List[str]) -> bool:
    """Heuristic: if any of the critical keywords are present, trigger reaction.
    Controlled vocabulary can be extended; this is intentionally simple.
    """
    if not tags:
        return False
    critical = {"gesetz", "krieg", "gefahr", "notstand", "krise", "warnung"}
    return any((t or "").lower() in critical for t in tags)


def run_crawler_loop(interval_seconds: int = 3600):
    while True:
        try:
            run_crawler_once()
            promote_crawled_to_blocks()
        except Exception:
            pass
        time.sleep(interval_seconds)
