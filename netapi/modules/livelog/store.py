from __future__ import annotations

import asyncio
import json
import time
from collections import Counter, deque
from dataclasses import dataclass
from threading import Lock
from typing import Any, Deque, Dict, List, Optional


def _iso_now() -> str:
    # Use an ISO-ish timestamp; keep it simple and stable.
    try:
        import datetime as _dt

        return _dt.datetime.now(_dt.timezone.utc).isoformat()
    except Exception:
        return str(int(time.time()))


def _safe_str(v: Any, *, limit: int = 500) -> str:
    try:
        s = str(v)
    except Exception:
        return ""
    return s[:limit]


@dataclass
class LiveLogConfig:
    max_events: int = 10_000
    subscriber_queue_size: int = 500


class LiveLogStore:
    def __init__(self, cfg: LiveLogConfig | None = None):
        self._cfg = cfg or LiveLogConfig()
        self._lock = Lock()
        self._events: Deque[Dict[str, Any]] = deque(maxlen=int(self._cfg.max_events))
        self._subscribers: List[asyncio.Queue] = []

    def add(self, event: Dict[str, Any]) -> Dict[str, Any]:
        evt = dict(event or {})
        evt.setdefault("ts", _iso_now())
        evt.setdefault("kind", "event")

        # Light redaction/normalization for safety
        if "cmd" in evt:
            evt["cmd"] = _safe_str(evt.get("cmd"), limit=600)
        if "path" in evt:
            evt["path"] = _safe_str(evt.get("path"), limit=600)

        with self._lock:
            self._events.append(evt)
            subs = list(self._subscribers)

        # Fan out without blocking.
        for q in subs:
            try:
                if q.full():
                    try:
                        q.get_nowait()
                    except Exception:
                        pass
                q.put_nowait(evt)
            except Exception:
                continue

        return evt

    def tail(self, limit: int = 200) -> List[Dict[str, Any]]:
        try:
            limit_i = max(0, min(int(limit), 10_000))
        except Exception:
            limit_i = 200
        with self._lock:
            data = list(self._events)
        return data[-limit_i:] if limit_i else []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=int(self._cfg.subscriber_queue_size))
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def stats(self, *, window: int = 2000, top: int = 20) -> Dict[str, Any]:
        try:
            window_i = max(0, min(int(window), int(self._cfg.max_events)))
        except Exception:
            window_i = 2000
        try:
            top_i = max(1, min(int(top), 200))
        except Exception:
            top_i = 20

        rows = self.tail(window_i)
        by_pid = Counter()
        by_cmd = Counter()
        by_container = Counter()
        by_kind = Counter()

        for e in rows:
            try:
                kind = e.get("kind")
                if kind:
                    by_kind[_safe_str(kind, limit=120)] += 1
                pid = e.get("pid")
                if pid is not None and str(pid).strip() != "":
                    by_pid[_safe_str(pid, limit=40)] += 1
                cmd = e.get("cmd")
                if cmd:
                    by_cmd[_safe_str(cmd, limit=200)] += 1
                container = e.get("container")
                if container:
                    by_container[_safe_str(container, limit=120)] += 1
            except Exception:
                continue

        def _top(counter: Counter) -> List[Dict[str, Any]]:
            return [{"key": k, "count": int(v)} for (k, v) in counter.most_common(top_i)]

        return {
            "ok": True,
            "window": int(window_i),
            "total": int(len(rows)),
            "by_kind": _top(by_kind),
            "by_pid": _top(by_pid),
            "by_container": _top(by_container),
            "by_cmd": _top(by_cmd),
        }


STORE = LiveLogStore()
STORE.add({"kind": "livelog", "level": "info", "msg": "livelog store ready"})


def emit(kind: str, **fields: Any) -> Dict[str, Any]:
    evt: Dict[str, Any] = {"kind": kind}
    evt.update(fields)
    return STORE.add(evt)


def dumps_sse(evt: Dict[str, Any]) -> str:
    # One SSE event with a JSON payload.
    payload = json.dumps(evt, ensure_ascii=False, separators=(",", ":"))
    return f"data: {payload}\n\n"
