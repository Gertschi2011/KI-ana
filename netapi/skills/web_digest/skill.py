from __future__ import annotations
import json, time
from typing import Dict, Any, List
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Minimaler Fetch ohne externe Libs
UA = "KI_ana/0.1 (+web_digest)"

SITES = [
    ("https://hnrss.org/frontpage.jsonfeed", "Hacker News"),
    ("https://www.tagesschau.de/index~rss2.xml", "tagesschau.de (RSS)"),
]

def _http_get(url: str, timeout: float = 6.0) -> bytes:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as r:
        return r.read()

def _try_parse_json(data: bytes) -> Dict[str, Any] | None:
    try:
        return json.loads(data.decode("utf-8", "replace"))
    except Exception:
        return None

def _extract_hn(jsonfeed: Dict[str, Any]) -> List[str]:
    items = (jsonfeed or {}).get("items") or []
    titles = []
    for it in items[:2]:
        t = (it.get("title") or "").strip()
        if t: titles.append(t)
    return titles

def _extract_rss_titles(xml_bytes: bytes) -> List[str]:
    # super-leichtgewichtige Titel-Extraktion (kein echtes XML-Parsing, robust genug)
    txt = xml_bytes.decode("utf-8", "replace")
    out: List[str] = []
    for chunk in txt.split("<item"):
        if "<title>" in chunk:
            t = chunk.split("<title>",1)[1].split("</title>",1)[0]
            t = t.replace("<![CDATA[","").replace("]]>","").strip()
            if t and t.lower() != "title":
                out.append(t)
        if len(out) >= 2:
            break
    return out

def _save_block(title: str, content: str, tags: list[str], url: str | None = None) -> Dict[str, Any]:
    # 1) bevorzugt globalen memory_store, wenn vorhanden
    try:
        from netapi import memory_store as _mem
        if hasattr(_mem, "add_block"):
            bid = _mem.add_block(title=title, content=content, tags=tags, url=url)
            if isinstance(bid, str) and bid:
                return {"ok": True, "id": bid, "file": f"{bid}.json", "url": url or ""}
    except Exception:
        pass

    # 2) Fallback: über chat.memory_adapter.store auf die Long-Term-Blocks schreiben
    try:
        from netapi.modules.chat.memory_adapter import store as store_block
        p = store_block(title=title, content=content, tags=tags, url=url, meta={"source": "skill:web_digest"})
        return {"ok": True, "file": str(p)}
    except Exception as e:
        return {"ok": False, "error": f"store_failed: {e}"}

def run(action: str, args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Entry: action in {"scheduled","digest_now"}.
    """
    if action not in {"scheduled", "digest_now"}:
        return {"ok": False, "error": "unsupported_action", "action": action}

    headlines: List[str] = []
    errors: List[str] = []

    for url, label in SITES:
        try:
            raw = _http_get(url)
            if url.endswith(".json") or "jsonfeed" in url:
                data = _try_parse_json(raw) or {}
                titles = _extract_hn(data)
            else:
                titles = _extract_rss_titles(raw)
            if titles:
                headlines.extend([f"{label}: {t}" for t in titles])
        except (URLError, HTTPError) as e:
            errors.append(f"{label}: {e}")
        except Exception as e:
            errors.append(f"{label}: {e}")

    if not headlines and errors:
        return {"ok": False, "error": "fetch_failed", "details": errors}

    ts = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    content = " • " + "\n • ".join(headlines)
    save = _save_block(
        title=f"Web Digest {ts}",
        content=content,
        tags=["digest","web","news"],
        url=None
    )

    return {
        "ok": True,
        "headlines": headlines,
        "saved": save,
        "errors": errors,
        "meta": {"action": action, "skill": ctx.get("skill")}
    }
