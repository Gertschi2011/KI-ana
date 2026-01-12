from __future__ import annotations

import os
import threading
import time

from celery import Celery
from celery.signals import worker_ready, worker_shutdown

REDIS_URL = f"redis://{os.getenv('REDIS_HOST','redis')}:{os.getenv('REDIS_PORT','6379')}/0"

celery = Celery(
    "kiana",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.workers.tasks"],
)

celery.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"]) 


_HB_STOP = threading.Event()
_HB_THREAD: threading.Thread | None = None


def _heartbeat_loop() -> None:
    try:
        import redis  # type: ignore
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=1, socket_connect_timeout=1)
    except Exception:
        return

    key = "kiana:worker:heartbeat"
    while not _HB_STOP.is_set():
        try:
            now = int(time.time())
            # TTL keeps the key from becoming stale forever.
            r.set(key, now, ex=60)
        except Exception:
            pass
        _HB_STOP.wait(5.0)


@worker_ready.connect
def _on_worker_ready(**_kwargs):
    global _HB_THREAD
    try:
        if _HB_THREAD and _HB_THREAD.is_alive():
            return
        _HB_STOP.clear()
        _HB_THREAD = threading.Thread(target=_heartbeat_loop, name="worker-heartbeat", daemon=True)
        _HB_THREAD.start()
    except Exception:
        return


@worker_shutdown.connect
def _on_worker_shutdown(**_kwargs):
    try:
        _HB_STOP.set()
    except Exception:
        return
