from __future__ import annotations

import threading
import time
from typing import Dict, Tuple


_lock = threading.Lock()

# Keyed by (route, method, status)
_http_requests_total: Dict[Tuple[str, str, int], int] = {}

# Sums by (route, method)
_http_request_duration_seconds_sum: Dict[Tuple[str, str], float] = {}

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

        lines.append("# HELP ki_ana_limits_exceeded_total Total rate/limit exceed events")
        lines.append("# TYPE ki_ana_limits_exceeded_total counter")
        for (feature, scope), count in sorted(_limits_exceeded_total.items()):
            f = _escape_label(feature)
            sc = _escape_label(scope)
            lines.append(f"ki_ana_limits_exceeded_total{{feature=\"{f}\",scope=\"{sc}\"}} {int(count)}")

    lines.append("")
    return "\n".join(lines)


def _escape_label(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
