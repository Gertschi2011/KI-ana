from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path

router = APIRouter(tags=["events"])

BASE_DIR = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
BUS_PATH = BASE_DIR / "system" / "events_bus.py"

def _load_bus():
    return SourceFileLoader("events_bus", str(BUS_PATH)).load_module()  # type: ignore

@router.get("/events")
async def sse_events(request: Request):
    bus = _load_bus()
    q = await bus.subscribe()  # type: ignore

    async def gen():
        try:
            # Send an initial keep-alive ping so proxies/clients don't time out before first event
            try:
                yield b": ping\n\n"
            except Exception:
                pass
            while True:
                if await request.is_disconnected():
                    break
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # comment ping to keep connection alive
                    yield b": keep-alive\n\n"
                    continue
                data = json.dumps(evt, ensure_ascii=False)
                yield f"data: {data}\n\n".encode("utf-8")
        finally:
            try:
                await bus.unsubscribe(q)  # type: ignore
            except Exception:
                pass

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
