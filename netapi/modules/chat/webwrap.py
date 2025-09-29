from typing import List, Tuple, Optional, Dict
try:
    from ...web_qa import answer_from_web as _answer_from_web
    from ...web_qa import web_search as _web_search
except Exception:
    _answer_from_web = None
    _web_search = None

def answer_with_sources(q: str, limit: int = 5) -> Tuple[Optional[str], List[Dict]]:
    if _answer_from_web:
        try:
            ans, sources = _answer_from_web(q, limit=limit)
            return (ans or None), (sources or [])
        except Exception:
            pass
    if _web_search:
        try:
            items = _web_search(q, limit=limit)
            return None, (items or [])
        except Exception:
            pass
    return None, []

def format_sources(sources: List[dict], limit: int = 2) -> str:
    if not sources:
        return ""
    out = []
    for s in sources[:limit]:
        title = s.get("title") or s.get("site") or "Quelle"
        url = s.get("url") or s.get("link") or ""
        out.append(f"- {title} ({url})")
    return "\n\nQuellen:\n" + "\n".join(out)