from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from netapi.deps import get_current_user_required, require_admin_area

from .store import STORE, dumps_sse


router = APIRouter(prefix="/api/livelog", tags=["livelog"])


def _guard(user: Dict[str, Any] | None) -> None:
    # Creator/Admin only (creator is treated as admin-area in deps).
    require_admin_area(user)


@router.get("/tail")
def tail(
    limit: int = Query(200, ge=0, le=10_000),
    user: Dict[str, Any] = Depends(get_current_user_required),
):
    _guard(user)
    return {"ok": True, "items": STORE.tail(limit)}


@router.get("/stats")
def stats(
    window: int = Query(2000, ge=0, le=10_000),
    top: int = Query(20, ge=1, le=200),
    user: Dict[str, Any] = Depends(get_current_user_required),
):
    _guard(user)
    return STORE.stats(window=window, top=top)


@router.post("/event")
async def ingest_event(
    body: Dict[str, Any],
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user_required),
):
    """Ingest a single event into the ringbuffer.

    Intended for internal automation/sidecars. Protected by Creator/Admin.
    """
    _guard(user)

    if not isinstance(body, dict):
        raise HTTPException(400, "invalid payload")

    # Minimal origin hints (safe defaults)
    try:
        body.setdefault("src", "api")
        body.setdefault("remote", request.client.host if request.client else None)
    except Exception:
        pass

    evt = STORE.add(body)
    return {"ok": True, "event": evt}


@router.get("/stream")
async def stream(
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user_required),
):
    _guard(user)

    q = STORE.subscribe()

    async def gen():
        # send a quick comment so proxies flush early
        yield ": livelog stream\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    evt = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield dumps_sse(evt)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            STORE.unsubscribe(q)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
