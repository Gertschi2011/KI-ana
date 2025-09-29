#!/usr/bin/env python3
from __future__ import annotations
import asyncio
from typing import List, Dict, Any

# Very small in-process pub/sub for events (e.g., new blocks)
_subscribers: List[asyncio.Queue] = []
_lock = asyncio.Lock()

async def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    async with _lock:
        _subscribers.append(q)
    return q

async def unsubscribe(q: asyncio.Queue) -> None:
    async with _lock:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass

def publish(event: Dict[str, Any]) -> None:
    # Fire-and-forget; put_nowait to every subscriber
    for q in list(_subscribers):
        try:
            q.put_nowait(event)
        except Exception:
            # drop slow/broken subscriber
            try:
                _subscribers.remove(q)
            except Exception:
                pass
