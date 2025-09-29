# netapi/logging_bridge.py
from __future__ import annotations
import asyncio
import logging
from collections import deque
from typing import Deque, Optional, AsyncIterator

# A small in-memory ring buffer for recent log lines
class RingBuffer:
    def __init__(self, maxlen: int = 5000):
        self._buf: Deque[str] = deque(maxlen=maxlen)
        self._lock = asyncio.Lock()

    async def append(self, line: str) -> None:
        async with self._lock:
            self._buf.append(line)

    async def snapshot(self, n: int = 1000) -> list[str]:
        async with self._lock:
            if n <= 0 or n >= len(self._buf):
                return list(self._buf)
            return list(self._buf)[-n:]

# Global ring buffer and broadcaster queue
RING = RingBuffer(maxlen=8000)

class AsyncLogHandler(logging.Handler):
    """Logging handler that forwards records into an asyncio Queue and ring buffer."""
    def __init__(self, queue: asyncio.Queue[str]):
        super().__init__()
        self.queue = queue
        self.formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            # Non-async context here; use create_task to not block
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(RING.append(line))
                # Try non-blocking put; if it fails, drop line to avoid backpressure
                try:
                    self.queue.put_nowait(line)
                except asyncio.QueueFull:
                    pass
            except RuntimeError:
                # No running loop; best-effort append only
                try:
                    import threading
                    # Fallback buffer append without lock if no loop
                    RING._buf.append(line)  # type: ignore[attr-defined]
                except Exception:
                    pass
        except Exception:
            # Never raise from emit
            pass

class LogBroadcaster:
    def __init__(self, max_queue: int = 2048):
        self.queue: asyncio.Queue[str] = asyncio.Queue(max_queue)
        self.handler = AsyncLogHandler(self.queue)
        self._installed = False

    def install(self) -> None:
        if self._installed:
            return
        root = logging.getLogger()
        root.addHandler(self.handler)
        # Ensure INFO level or lower shows up
        if root.level > logging.INFO:
            root.setLevel(logging.INFO)
        self._installed = True

    async def stream(self) -> AsyncIterator[str]:
        """Async generator yielding log lines as they arrive."""
        while True:
            line = await self.queue.get()
            yield line

BROADCASTER = LogBroadcaster()
