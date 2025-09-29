# netapi/modules/web/router.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Callable

router = APIRouter()

# Neue API nutzt web_search_and_summarize + web_enrich_and_store
try:
    from ...web_qa import web_search_and_summarize as _web_sum
except Exception:
    _web_sum = None
try:
    from ...web_qa import web_enrich_and_store as _web_enrich
except Exception:
    _web_enrich = None

class WebSearchIn(BaseModel):
    query: str = Field(min_length=2)
    max_results: int = 5

class WebQAIn(BaseModel):
    question: str = Field(min_length=3)
    max_results: int = 5

@router.post("/web/search")
def web_search(body: WebSearchIn, request: Request):
    ip = request.client.host if request.client else "?"
    if not _rate_allow(ip, "web", limit=20, per_seconds=300):
        raise HTTPException(429, "rate limit: 20/5min per IP")
    if _web_sum is None:
        raise HTTPException(501, "web search backend not available")
    try:
        res = _web_sum(body.query, user_context={"lang": "de"}, max_results=body.max_results)
        return {"ok": True, **res}
    except Exception as e:
        raise HTTPException(500, f"web search failed: {e}")

@router.post("/web/qa")
def web_qa(body: WebQAIn, request: Request):
    ip = request.client.host if request.client else "?"
    if not _rate_allow(ip, "web", limit=20, per_seconds=300):
        raise HTTPException(429, "rate limit: 20/5min per IP")
    if _web_sum is None:
        raise HTTPException(501, "web QA backend not available")
    try:
        res = _web_sum(body.question, user_context={"lang": "de"}, max_results=body.max_results)
        # Kompakte Antwort bauen
        items = res.get("results") or []
        answer = None
        if items:
            parts = []
            for it in items[:2]:
                if it.get("summary"):
                    parts.append(it["summary"])
            answer = "\n\n".join(parts) if parts else None
        return {"ok": True, "answer": answer, "sources": items}
    except Exception as e:
        raise HTTPException(500, f"web qa failed: {e}")

@router.post("/web/enrich")
def web_enrich(body: WebSearchIn, request: Request):
    ip = request.client.host if request.client else "?"
    if not _rate_allow(ip, "web", limit=10, per_seconds=300):
_RATE: dict[str, list[float]] = {}

def _rate_allow(ip: str, key: str, *, limit: int = 20, per_seconds: int = 300) -> bool:
    import time
    now = time.time()
    bucket = _RATE.setdefault(f"{ip}:{key}", [])
    while bucket and now - bucket[0] > per_seconds:
        bucket.pop(0)
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True
        raise HTTPException(429, "rate limit: 10/5min per IP")
    if _web_enrich is None:
        raise HTTPException(501, "web enrich backend not available")
    try:
        # Falls Memory-Writer gewünscht ist, reich ihn hier ein; aktuell nutzt die Funktion optionalen Writer
        res = _web_enrich(body.query, memory_writer=None, user_context={"lang": "de"})
        return {"ok": True, **res}
    except Exception as e:
        raise HTTPException(500, f"web enrich failed: {e}")
