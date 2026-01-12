from __future__ import annotations

import os
import threading
import time

from celery import Celery
from celery.schedules import crontab
from celery.signals import (
    task_failure,
    task_postrun,
    task_prerun,
    task_retry,
    task_success,
    worker_init,
    worker_ready,
    worker_shutdown,
)

REDIS_URL = f"redis://{os.getenv('REDIS_HOST','redis')}:{os.getenv('REDIS_PORT','6379')}/0"

celery = Celery(
    "kiana",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.workers.tasks"],
)

celery.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"]) 


# ---- Periodic tasks (Phase D2: retention enforcement) --------------------
def _int_env(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, str(default))).strip() or str(default))
    except Exception:
        return int(default)


celery.conf.timezone = str(os.getenv("TZ", "UTC") or "UTC")
celery.conf.enable_utc = True

_retention_minute = max(0, min(59, _int_env("RETENTION_PURGE_MINUTE", 25)))
_retention_hour = max(0, min(23, _int_env("RETENTION_PURGE_HOUR", 3)))

celery.conf.beat_schedule = {
    "retention_purge_daily": {
        "task": "maintenance.retention_purge",
        "schedule": crontab(minute=_retention_minute, hour=_retention_hour),
    },
}


_HB_STOP = threading.Event()
_HB_THREAD: threading.Thread | None = None


# ---- Task SLIs (Phase E: Celery runtime/failures) -------------------------
_TASK_STARTS_LOCK = threading.Lock()
_TASK_STARTS: dict[str, float] = {}

_RUNTIME_BUCKETS: tuple[float, ...] = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0)


def _task_label(task) -> str:
    try:
        name = getattr(task, "name", None)
        if name:
            return str(name)
    except Exception:
        pass
    return "unknown"


def _bucket_le_label(duration_seconds: float) -> str:
    d = float(duration_seconds)
    for b in _RUNTIME_BUCKETS:
        if d <= b:
            # Keep labels stable and compact
            s = ("{:.3f}".format(float(b))).rstrip("0").rstrip(".")
            return s
    return "+Inf"


_REDIS_CLIENT = None
_REDIS_CLIENT_LOCK = threading.Lock()


def _redis_client():
    global _REDIS_CLIENT
    with _REDIS_CLIENT_LOCK:
        if _REDIS_CLIENT is not None:
            return _REDIS_CLIENT
        try:
            import redis  # type: ignore

            _REDIS_CLIENT = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=0.5, socket_connect_timeout=0.5)
        except Exception:
            _REDIS_CLIENT = None
        return _REDIS_CLIENT


def _redis_hincrby_clamped(r, key: str, field: str, delta: int) -> None:
    try:
        new_val = int(r.hincrby(key, field, int(delta)))
        if new_val < 0:
            r.hset(key, field, 0)
    except Exception:
        return


def _metrics_keys() -> dict[str, str]:
    return {
        "task_total": "kiana:metrics:celery:task_total",
        "task_retries_total": "kiana:metrics:celery:task_retries_total",
        "task_runtime_bucket": "kiana:metrics:celery:task_runtime_bucket",
        "task_runtime_sum": "kiana:metrics:celery:task_runtime_sum",
        "task_runtime_count": "kiana:metrics:celery:task_runtime_count",
        "task_inflight": "kiana:metrics:celery:task_inflight",
        "agg_last_update_ts": "kiana:metrics:celery:agg_last_update_ts",
    }


def _mark_task_agg_updated(r, *, task_name: str) -> None:
    try:
        now = int(time.time())
        keys = _metrics_keys()
        r.hset(keys["agg_last_update_ts"], str(task_name), now)
    except Exception:
        return


def _maybe_reset_metrics_on_start() -> None:
    try:
        if str(os.getenv("KI_ANA_METRICS_REDIS_RESET_ON_START", "0")).strip() != "1":
            return
    except Exception:
        return

    r = _redis_client()
    if not r:
        return

    try:
        prefix = str(os.getenv("KI_ANA_METRICS_REDIS_RESET_PREFIX", "kiana:metrics:celery:")).strip() or "kiana:metrics:celery:"
    except Exception:
        prefix = "kiana:metrics:celery:"

    lock_key = f"{prefix}reset_lock"
    try:
        acquired = bool(r.set(lock_key, "1", nx=True, ex=60))
    except Exception:
        acquired = False
    if not acquired:
        return

    deleted = 0
    try:
        cursor = 0
        pattern = f"{prefix}*"
        while True:
            cursor, keys = r.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                try:
                    r.delete(*keys)
                    deleted += int(len(keys))
                except Exception:
                    pass
            if int(cursor) == 0:
                break
    except Exception:
        pass

    try:
        print(f"metrics redis reset done: {deleted} keys (prefix={prefix})")
    except Exception:
        pass


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


@task_prerun.connect
def _on_task_prerun(task_id=None, task=None, **_kwargs):
    tid = str(task_id or "").strip()
    if not tid:
        return
    now = time.time()
    with _TASK_STARTS_LOCK:
        _TASK_STARTS[tid] = now

    r = _redis_client()
    if not r:
        return
    name = _task_label(task)
    keys = _metrics_keys()
    _redis_hincrby_clamped(r, keys["task_inflight"], name, 1)
    _mark_task_agg_updated(r, task_name=name)


@task_postrun.connect
def _on_task_postrun(task_id=None, task=None, **_kwargs):
    tid = str(task_id or "").strip()
    r = _redis_client()
    name = _task_label(task)

    started = None
    if tid:
        with _TASK_STARTS_LOCK:
            started = _TASK_STARTS.pop(tid, None)

    if r:
        keys = _metrics_keys()
        _redis_hincrby_clamped(r, keys["task_inflight"], name, -1)
        _mark_task_agg_updated(r, task_name=name)

        if isinstance(started, (int, float)):
            dur = max(0.0, float(time.time() - float(started)))
            le = _bucket_le_label(dur)
            try:
                r.hincrby(keys["task_runtime_bucket"], f"{name}|{le}", 1)
                r.hincrbyfloat(keys["task_runtime_sum"], name, float(dur))
                r.hincrby(keys["task_runtime_count"], name, 1)
                _mark_task_agg_updated(r, task_name=name)
            except Exception:
                return


@task_success.connect
def _on_task_success(sender=None, **_kwargs):
    r = _redis_client()
    if not r:
        return
    name = _task_label(sender)
    keys = _metrics_keys()
    try:
        r.hincrby(keys["task_total"], f"{name}|success", 1)
        _mark_task_agg_updated(r, task_name=name)
    except Exception:
        return


@task_failure.connect
def _on_task_failure(sender=None, **_kwargs):
    r = _redis_client()
    if not r:
        return
    name = _task_label(sender)
    keys = _metrics_keys()
    try:
        r.hincrby(keys["task_total"], f"{name}|failure", 1)
        _mark_task_agg_updated(r, task_name=name)
    except Exception:
        return


@task_retry.connect
def _on_task_retry(sender=None, **_kwargs):
    r = _redis_client()
    if not r:
        return
    name = _task_label(sender)
    keys = _metrics_keys()
    try:
        r.hincrby(keys["task_retries_total"], name, 1)
        _mark_task_agg_updated(r, task_name=name)
    except Exception:
        return


@worker_init.connect
def _on_worker_init(**_kwargs):
    try:
        _maybe_reset_metrics_on_start()
    except Exception:
        return


@worker_ready.connect
def _on_worker_ready(**_kwargs):
    global _HB_THREAD
    try:
        _maybe_reset_metrics_on_start()
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
