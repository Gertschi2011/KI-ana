from __future__ import annotations
from flask import Blueprint, Response
import time

bp = Blueprint("logs", __name__)


def _sse_format(data: str) -> str:
    return f"data: {data}\n\n"


@bp.get("/stream")
def stream():
    def gen():
        # Simple heartbeat stream; replace with real log feed if available
        yield _sse_format("connected")
        i = 0
        while True:
            i += 1
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            yield _sse_format(f"[{now}] heartbeat {i}")
            time.sleep(2)
    return Response(gen(), mimetype="text/event-stream")
