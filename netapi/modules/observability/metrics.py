from __future__ import annotations

import math
import threading
import time
from collections import deque
from typing import Deque, Dict, Iterable, List, Optional, Tuple


_lock = threading.Lock()

# Keyed by (route, method, status)
_http_requests_total: Dict[Tuple[str, str, int], int] = {}

# Sums by (route, method)
_http_request_duration_seconds_sum: Dict[Tuple[str, str], float] = {}

# Counts by (route, method)
_http_request_duration_seconds_count: Dict[Tuple[str, str], int] = {}

# Recent requests for rolling-window stats. Keyed by (ts, route, method, status, duration_seconds)
_recent_requests: Deque[Tuple[float, str, str, int, float]] = deque(maxlen=20000)

# Keyed by (feature, scope)
_limits_exceeded_total: Dict[Tuple[str, str], int] = {}

_started_at = time.time()


def record_http_request(*, route: str, method: str, status: int, duration_seconds: float, latency_ms: float | None = None) -> None:
    """Record a single HTTP request (best-effort).

    This is intentionally minimal: in-process counters only.
    """
    try:
        r = str(route or "/")
        m = str(method or "GET").upper()
        s = int(status)
        d = float(duration_seconds)
    except Exception:
        return

    with _lock:
        _http_requests_total[(r, m, s)] = _http_requests_total.get((r, m, s), 0) + 1
        _http_request_duration_seconds_sum[(r, m)] = _http_request_duration_seconds_sum.get((r, m), 0.0) + d
        _http_request_duration_seconds_count[(r, m)] = _http_request_duration_seconds_count.get((r, m), 0) + 1
        _recent_requests.append((time.time(), r, m, s, d))


def inc_limits_exceeded(*, feature: str, scope: str) -> None:
    try:
        f = str(feature or "").strip().lower() or "unknown"
        sc = str(scope or "").strip().lower() or "unknown"
    except Exception:
        return
    with _lock:
        _limits_exceeded_total[(f, sc)] = _limits_exceeded_total.get((f, sc), 0) + 1


def render_prometheus_text() -> str:
    """Render a minimal Prometheus exposition string."""
    lines: list[str] = []
    now = time.time()

    lines.append("# HELP ki_ana_process_uptime_seconds Process uptime in seconds")
    lines.append("# TYPE ki_ana_process_uptime_seconds gauge")
    lines.append(f"ki_ana_process_uptime_seconds {max(0.0, now - _started_at):.3f}")

    lines.append("# HELP ki_ana_http_requests_total Total HTTP requests")
    lines.append("# TYPE ki_ana_http_requests_total counter")
    with _lock:
        for (route, method, status), count in sorted(_http_requests_total.items()):
            r = _escape_label(route)
            m = _escape_label(method)
            lines.append(f"ki_ana_http_requests_total{{route=\"{r}\",method=\"{m}\",status=\"{status}\"}} {int(count)}")

        lines.append("# HELP ki_ana_http_request_duration_seconds_sum Total time spent handling requests")
        lines.append("# TYPE ki_ana_http_request_duration_seconds_sum counter")
        for (route, method), total in sorted(_http_request_duration_seconds_sum.items()):
            r = _escape_label(route)
            m = _escape_label(method)
            lines.append(f"ki_ana_http_request_duration_seconds_sum{{route=\"{r}\",method=\"{m}\"}} {float(total):.6f}")

        lines.append("# HELP ki_ana_http_request_duration_seconds_count Total number of observed requests")
        lines.append("# TYPE ki_ana_http_request_duration_seconds_count counter")
        for (route, method), cnt in sorted(_http_request_duration_seconds_count.items()):
            r = _escape_label(route)
            m = _escape_label(method)
            lines.append(f"ki_ana_http_request_duration_seconds_count{{route=\"{r}\",method=\"{m}\"}} {int(cnt)}")

        lines.append("# HELP ki_ana_limits_exceeded_total Total rate/limit exceed events")
        lines.append("# TYPE ki_ana_limits_exceeded_total counter")
        for (feature, scope), count in sorted(_limits_exceeded_total.items()):
            f = _escape_label(feature)
            sc = _escape_label(scope)
            lines.append(f"ki_ana_limits_exceeded_total{{feature=\"{f}\",scope=\"{sc}\"}} {int(count)}")

    lines.append("")
    return "\n".join(lines)


def uptime_seconds() -> float:
    try:
        return max(0.0, float(time.time() - _started_at))
    except Exception:
        return 0.0


def limits_exceeded_total() -> int:
    with _lock:
        return int(sum(int(v) for v in _limits_exceeded_total.values()))


def window_http_stats(*, window_seconds: int = 60, exclude_statuses: Optional[Iterable[int]] = None) -> Dict[str, float | int | None]:
    """Rolling-window HTTP stats computed from in-process recent requests.

    Notes:
    - Best-effort only (in-memory, per-process).
    - By default, excludes nothing from totals. Pass exclude_statuses (e.g. {401}) to compute SLO rates.
    """

    win = max(1, int(window_seconds or 60))
    now = time.time()
    cutoff = now - float(win)
    excl = set(int(s) for s in (exclude_statuses or []))

    total = 0
    ok2xx = 0
    err5xx = 0

    with _lock:
        for ts, _route, _method, status, _dur in _recent_requests:
            if ts < cutoff:
                continue
            if int(status) in excl:
                continue
            total += 1
            if 200 <= int(status) < 300:
                ok2xx += 1
            if int(status) >= 500:
                err5xx += 1

    if total <= 0:
        return {
            "window_seconds": win,
            "requests_total": 0,
            "requests_per_min": 0.0,
            "2xx_rate": None,
            "5xx_rate": None,
        }

    return {
        "window_seconds": win,
        "requests_total": int(total),
        "requests_per_min": float(total) * 60.0 / float(win),
        "2xx_rate": float(ok2xx) / float(total),
        "5xx_rate": float(err5xx) / float(total),
    }


def route_latency_quantiles(
    *,
    route: str,
    method: str | None = None,
    window_seconds: int = 3600,
    quantiles: Iterable[float] = (0.5, 0.95, 0.99),
) -> Dict[str, float | None]:
    """Compute latency quantiles for a specific route from the rolling window."""

    r = str(route or "/")
    m = str(method).upper() if method else None
    win = max(1, int(window_seconds or 3600))
    now = time.time()
    cutoff = now - float(win)

    samples: List[float] = []
    with _lock:
        for ts, rr, mm, _status, dur in _recent_requests:
            if ts < cutoff:
                continue
            if rr != r:
                continue
            if m and mm != m:
                continue
            try:
                samples.append(float(dur))
            except Exception:
                continue

    out: Dict[str, float | None] = {}
    qs = [float(q) for q in quantiles]
    if not samples:
        for q in qs:
            out[f"p{int(round(q*100))}"] = None
        return out

    samples.sort()
    n = len(samples)
    for q in qs:
        q2 = min(1.0, max(0.0, q))
        idx = int(math.ceil(q2 * n)) - 1
        idx = max(0, min(n - 1, idx))
        out[f"p{int(round(q2*100))}"] = float(samples[idx])
    return out


def window_route_status_counts(
    *,
    route: str,
    method: str | None = None,
    window_seconds: int = 3600,
    exclude_statuses: Optional[Iterable[int]] = None,
) -> Dict[str, int]:
    """Count statuses for a specific route within a rolling window."""
    r = str(route or "/")
    m = str(method).upper() if method else None
    win = max(1, int(window_seconds or 3600))
    now = time.time()
    cutoff = now - float(win)
    excl = set(int(s) for s in (exclude_statuses or []))
    total = 0
    ok2xx = 0
    err5xx = 0
    with _lock:
        for ts, rr, mm, status, _dur in _recent_requests:
            if ts < cutoff:
                continue
            if rr != r:
                continue
            if m and mm != m:
                continue
            if int(status) in excl:
                continue
            total += 1
            if 200 <= int(status) < 300:
                ok2xx += 1
            if int(status) >= 500:
                err5xx += 1
    return {"total": int(total), "ok2xx": int(ok2xx), "err5xx": int(err5xx)}


def _escape_label(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
