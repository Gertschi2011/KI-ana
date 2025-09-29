# netapi/modules/logs/router.py
from __future__ import annotations
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, JSONResponse
from typing import AsyncIterator

# SSE optional import
try:
    from sse_starlette.sse import EventSourceResponse  # type: ignore
except Exception:
    EventSourceResponse = None  # type: ignore

from ...logging_bridge import BROADCASTER, RING

router = APIRouter(prefix="/api/logs", tags=["logs"]) 

@router.get("")
async def tail_logs(n: int = Query(500, ge=1, le=5000)):
    """Return the last N log lines from the in-memory ring buffer."""
    lines = await RING.snapshot(n)
    return {"ok": True, "lines": lines}

@router.get("/stream")
async def stream_logs():
    """Stream logs via SSE if sse_starlette is available; otherwise, fallback to chunked streaming."""
    async def gen() -> AsyncIterator[dict]:
        async for line in BROADCASTER.stream():
            yield {"data": line}

    if EventSourceResponse is not None:
        return EventSourceResponse(gen(), ping=15)

    # Fallback: chunked transfer (not true SSE)
    async def chunked():
        async for line in BROADCASTER.stream():
            yield (line + "\n").encode("utf-8")
    return StreamingResponse(chunked(), media_type="text/plain")
