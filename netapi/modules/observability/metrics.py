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


# ---- MetaMind KPIs (chat/product metrics) ---------------------------------
# Counter keyed by (tool, ok)
_chat_tool_calls_total: Dict[Tuple[str, str], int] = {}

# Counter keyed by (kind, decision)
_learning_consent_total: Dict[Tuple[str, str], int] = {}

# Counter keyed by (status)
_chat_feedback_total: Dict[Tuple[str], int] = {}

# Counter keyed by (kind)
_chat_correction_reversion_total: Dict[Tuple[str], int] = {}

# Counter keyed by (intent)
_chat_answers_without_sources_total: Dict[Tuple[str], int] = {}

# Counter keyed by (gate, mode)
_quality_gate_total: Dict[Tuple[str, str], int] = {}

# Export stable label sets so dashboards don't show "No data" before first hit.
_KNOWN_QUALITY_GATES: Tuple[str, ...] = (
    "sources_required",
    "learning_cooldown",
    "tools_disabled",
)
_KNOWN_QUALITY_GATE_MODES: Tuple[str, ...] = ("observed", "enforced")

# Histogram keyed by (intent, le_bucket)
_chat_answer_duration_seconds_bucket: Dict[Tuple[str, float], int] = {}
_chat_answer_duration_seconds_sum: Dict[Tuple[str], float] = {}
_chat_answer_duration_seconds_count: Dict[Tuple[str], int] = {}


# ---- Route grouping (Phase E: SLO-ready histograms) ------------------------
_ROUTE_GROUP_BUCKETS: Tuple[float, ...] = (
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    1.5,
    2.0,
    3.0,
    5.0,
    10.0,
)

# Histogram counters keyed by (route_group, method, le_bucket)
_http_duration_bucket: Dict[Tuple[str, str, float], int] = {}
# Sums and counts keyed by (route_group, method)
_http_duration_sum_by_group: Dict[Tuple[str, str], float] = {}
_http_duration_count_by_group: Dict[Tuple[str, str], int] = {}


def _route_group(path: str) -> str:
    p = (str(path or "/") or "/").strip()
    if not p.startswith("/"):
        p = "/" + p

    # Chat
    if p.startswith("/api/v2/chat") or p.startswith("/api/chat") or p.startswith("/api/agent/"):
        return "chat"

    # Auth
    if p.startswith("/api/auth/") or p in {"/api/login", "/api/me", "/api/logout"}:
        return "login"

    # Ops/metrics/health
    if p.startswith("/_/") or p == "/health" or p.startswith("/api/metrics") or p.startswith("/api/ops"):
        return "ops"

    # Learning
    if p.startswith("/api/v2/learning"):
        return "learning"

    # Viewer
    if p.startswith("/viewer"):
        return "viewer"

    # Admin/system tools
    if p.startswith("/api/system") or p.startswith("/api/crawler"):
        return "system"

    return "other"


def _bucket_le(duration_seconds: float) -> float:
    d = float(duration_seconds)
    for b in _ROUTE_GROUP_BUCKETS:
        if d <= b:
            return float(b)
    return float("inf")


# ---- Redis-backed liveness/queue and error counters ------------------------
_external_cache_lock = threading.Lock()
_external_cache_expires_at = 0.0
_external_cache: Dict[str, object] = {}


def inc_db_error(*, kind: str = "unknown") -> None:
    # Stores DB error counters as limits_exceeded style to avoid new global dicts
    try:
        k = str(kind or "unknown").strip().lower() or "unknown"
    except Exception:
        k = "unknown"
    inc_limits_exceeded(feature="db_error", scope=k)


def _refresh_external_cache() -> None:
    """Best-effort sampling of external health signals (fast, cached)."""
    global _external_cache_expires_at, _external_cache

    now = time.time()
    with _external_cache_lock:
        if now < _external_cache_expires_at:
            return

        data: Dict[str, object] = {}

        def _http_ok(url: str, *, timeout_s: float = 0.5) -> bool:
            try:
                from urllib.request import Request, urlopen

                req = Request(str(url), headers={"User-Agent": "ki-ana-metrics"})
                with urlopen(req, timeout=float(timeout_s)) as resp:
                    code = getattr(resp, "status", None)
                    if code is None:
                        return True
                    return 200 <= int(code) < 300
            except Exception:
                return False

        # Redis heartbeat + backlog
        try:
            import os as _os
            import redis  # type: ignore

            host = (_os.getenv("REDIS_HOST") or "redis").strip() or "redis"
            port = int((_os.getenv("REDIS_PORT") or "6379").strip() or 6379)
            r = redis.Redis(host=host, port=port, decode_responses=True, socket_timeout=0.5, socket_connect_timeout=0.5)

            # Dependency reachability
            try:
                data["dependency_redis_up"] = 1 if r.ping() else 0
            except Exception:
                data["dependency_redis_up"] = 0

            hb = r.get("kiana:worker:heartbeat")
            hb_ts = int(hb) if (hb and str(hb).isdigit()) else None
            if hb_ts is not None:
                age = max(0.0, float(now - float(hb_ts)))
                data["celery_worker_heartbeat_age_seconds"] = age
                data["celery_worker_up"] = 1 if age <= 20.0 else 0
            else:
                data["celery_worker_heartbeat_age_seconds"] = None
                data["celery_worker_up"] = 0

            # Default Celery queue in Redis broker is usually list key "celery"
            try:
                data["celery_queue_backlog"] = int(r.llen("celery"))
            except Exception:
                data["celery_queue_backlog"] = None

            # Celery task aggregates (written by worker signals)
            try:
                data["celery_task_total"] = dict(r.hgetall("kiana:metrics:celery:task_total"))
            except Exception:
                data["celery_task_total"] = {}
            try:
                data["celery_task_retries_total"] = dict(r.hgetall("kiana:metrics:celery:task_retries_total"))
            except Exception:
                data["celery_task_retries_total"] = {}
            try:
                data["celery_task_runtime_bucket"] = dict(r.hgetall("kiana:metrics:celery:task_runtime_bucket"))
            except Exception:
                data["celery_task_runtime_bucket"] = {}
            try:
                data["celery_task_runtime_sum"] = dict(r.hgetall("kiana:metrics:celery:task_runtime_sum"))
            except Exception:
                data["celery_task_runtime_sum"] = {}
            try:
                data["celery_task_runtime_count"] = dict(r.hgetall("kiana:metrics:celery:task_runtime_count"))
            except Exception:
                data["celery_task_runtime_count"] = {}
            try:
                data["celery_task_inflight"] = dict(r.hgetall("kiana:metrics:celery:task_inflight"))
            except Exception:
                data["celery_task_inflight"] = {}

            try:
                data["celery_agg_last_update_ts"] = dict(r.hgetall("kiana:metrics:celery:agg_last_update_ts"))
            except Exception:
                data["celery_agg_last_update_ts"] = {}
        except Exception:
            data["dependency_redis_up"] = 0
            data["celery_worker_heartbeat_age_seconds"] = None
            data["celery_worker_up"] = 0
            data["celery_queue_backlog"] = None
            data["celery_task_total"] = {}
            data["celery_task_retries_total"] = {}
            data["celery_task_runtime_bucket"] = {}
            data["celery_task_runtime_sum"] = {}
            data["celery_task_runtime_count"] = {}
            data["celery_task_inflight"] = {}
            data["celery_agg_last_update_ts"] = {}

        # Qdrant (HTTP)
        try:
            import os as _os

            qh = (_os.getenv("QDRANT_HOST") or "qdrant").strip() or "qdrant"
            qp = int((_os.getenv("QDRANT_PORT") or "6333").strip() or 6333)
            data["dependency_qdrant_up"] = 1 if _http_ok(f"http://{qh}:{qp}/healthz") else 0
        except Exception:
            data["dependency_qdrant_up"] = 0

        # MinIO (HTTP)
        try:
            import os as _os

            endpoint = (_os.getenv("MINIO_ENDPOINT") or "http://minio:9000").strip() or "http://minio:9000"
            endpoint = endpoint.rstrip("/")
            data["dependency_minio_up"] = 1 if _http_ok(f"{endpoint}/minio/health/live") else 0
        except Exception:
            data["dependency_minio_up"] = 0

        _external_cache = data
        _external_cache_expires_at = now + 5.0


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

        # Route-group histogram for p95/p99 per group
        try:
            g = _route_group(r)
            le = _bucket_le(d)
            _http_duration_bucket[(g, m, le)] = _http_duration_bucket.get((g, m, le), 0) + 1
            _http_duration_bucket[(g, m, float("inf"))] = _http_duration_bucket.get((g, m, float("inf")), 0) + 1
            _http_duration_sum_by_group[(g, m)] = _http_duration_sum_by_group.get((g, m), 0.0) + d
            _http_duration_count_by_group[(g, m)] = _http_duration_count_by_group.get((g, m), 0) + 1
        except Exception:
            pass


def inc_limits_exceeded(*, feature: str, scope: str) -> None:
    try:
        f = str(feature or "").strip().lower() or "unknown"
        sc = str(scope or "").strip().lower() or "unknown"
    except Exception:
        return
    with _lock:
        _limits_exceeded_total[(f, sc)] = _limits_exceeded_total.get((f, sc), 0) + 1


def inc_chat_tool_call(*, tool: str, ok: bool) -> None:
    try:
        t = str(tool or "unknown").strip().lower() or "unknown"
    except Exception:
        t = "unknown"
    status = "ok" if bool(ok) else "error"
    with _lock:
        _chat_tool_calls_total[(t, status)] = _chat_tool_calls_total.get((t, status), 0) + 1


def inc_learning_consent(*, kind: str, decision: str) -> None:
    try:
        k = str(kind or "unknown").strip().lower() or "unknown"
        d = str(decision or "unknown").strip().lower() or "unknown"
    except Exception:
        return
    with _lock:
        _learning_consent_total[(k, d)] = _learning_consent_total.get((k, d), 0) + 1


def inc_chat_feedback(*, status: str) -> None:
    try:
        s = str(status or "unknown").strip().lower() or "unknown"
    except Exception:
        s = "unknown"
    with _lock:
        _chat_feedback_total[(s,)] = _chat_feedback_total.get((s,), 0) + 1


def inc_chat_correction_reversion(*, kind: str = "feedback") -> None:
    try:
        k = str(kind or "feedback").strip().lower() or "feedback"
    except Exception:
        k = "feedback"
    with _lock:
        _chat_correction_reversion_total[(k,)] = _chat_correction_reversion_total.get((k,), 0) + 1


def inc_chat_answer_without_sources(*, intent: str) -> None:
    try:
        i = str(intent or "unknown").strip().lower() or "unknown"
    except Exception:
        i = "unknown"
    with _lock:
        _chat_answers_without_sources_total[(i,)] = _chat_answers_without_sources_total.get((i,), 0) + 1


def observe_chat_answer_duration_seconds(*, intent: str, duration_seconds: float) -> None:
    try:
        i = str(intent or "unknown").strip().lower() or "unknown"
        d = max(0.0, float(duration_seconds))
    except Exception:
        return
    le = _bucket_le(d)
    with _lock:
        _chat_answer_duration_seconds_bucket[(i, le)] = _chat_answer_duration_seconds_bucket.get((i, le), 0) + 1
        _chat_answer_duration_seconds_bucket[(i, float("inf"))] = _chat_answer_duration_seconds_bucket.get((i, float("inf")), 0) + 1
        _chat_answer_duration_seconds_sum[(i,)] = _chat_answer_duration_seconds_sum.get((i,), 0.0) + d
        _chat_answer_duration_seconds_count[(i,)] = _chat_answer_duration_seconds_count.get((i,), 0) + 1


def inc_quality_gate(*, gate: str, mode: str = "observed") -> None:
    try:
        g = str(gate or "unknown").strip().lower() or "unknown"
        m = str(mode or "observed").strip().lower() or "observed"
        if m not in {"observed", "enforced"}:
            m = "observed"
    except Exception:
        return
    with _lock:
        _quality_gate_total[(g, m)] = _quality_gate_total.get((g, m), 0) + 1


def render_prometheus_text() -> str:
    """Render a minimal Prometheus exposition string."""
    lines: list[str] = []
    now = time.time()

    # External (cached) gauges: worker health, queue backlog
    try:
        _refresh_external_cache()
    except Exception:
        pass

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

        # Route-group histogram for latency p95/p99
        lines.append("# HELP ki_ana_http_request_duration_seconds HTTP request duration histogram (route groups)")
        lines.append("# TYPE ki_ana_http_request_duration_seconds histogram")
        # buckets
        for (group, method, le), count in sorted(_http_duration_bucket.items()):
            g = _escape_label(group)
            m = _escape_label(method)
            le_label = "+Inf" if (isinstance(le, float) and math.isinf(le)) else ("{:.3f}".format(float(le)).rstrip("0").rstrip("."))
            lines.append(
                f"ki_ana_http_request_duration_seconds_bucket{{route_group=\"{g}\",method=\"{m}\",le=\"{le_label}\"}} {int(count)}"
            )
        # sum
        for (group, method), total in sorted(_http_duration_sum_by_group.items()):
            g = _escape_label(group)
            m = _escape_label(method)
            lines.append(f"ki_ana_http_request_duration_seconds_sum{{route_group=\"{g}\",method=\"{m}\"}} {float(total):.6f}")
        # count
        for (group, method), cnt in sorted(_http_duration_count_by_group.items()):
            g = _escape_label(group)
            m = _escape_label(method)
            lines.append(f"ki_ana_http_request_duration_seconds_count{{route_group=\"{g}\",method=\"{m}\"}} {int(cnt)}")

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

        # ---- MetaMind KPIs -------------------------------------------------
        lines.append("# HELP ki_ana_chat_tool_calls_total Chat tool calls (best-effort)")
        lines.append("# TYPE ki_ana_chat_tool_calls_total counter")
        for (tool, status), count in sorted(_chat_tool_calls_total.items()):
            t = _escape_label(tool)
            st = _escape_label(status)
            lines.append(f"ki_ana_chat_tool_calls_total{{tool=\"{t}\",status=\"{st}\"}} {int(count)}")

        lines.append("# HELP ki_ana_learning_consent_total Learning consent outcomes")
        lines.append("# TYPE ki_ana_learning_consent_total counter")
        for (kind, decision), count in sorted(_learning_consent_total.items()):
            k = _escape_label(kind)
            d = _escape_label(decision)
            lines.append(f"ki_ana_learning_consent_total{{kind=\"{k}\",decision=\"{d}\"}} {int(count)}")

        lines.append("# HELP ki_ana_chat_feedback_total Chat feedback outcomes")
        lines.append("# TYPE ki_ana_chat_feedback_total counter")
        for (status,), count in sorted(_chat_feedback_total.items()):
            st = _escape_label(status)
            lines.append(f"ki_ana_chat_feedback_total{{status=\"{st}\"}} {int(count)}")

        lines.append("# HELP ki_ana_chat_correction_reversion_total Corrections later reverted (best-effort)")
        lines.append("# TYPE ki_ana_chat_correction_reversion_total counter")
        for (kind,), count in sorted(_chat_correction_reversion_total.items()):
            k = _escape_label(kind)
            lines.append(f"ki_ana_chat_correction_reversion_total{{kind=\"{k}\"}} {int(count)}")

        lines.append("# HELP ki_ana_chat_answers_without_sources_total Hallucination proxy: factual-ish answers without sources")
        lines.append("# TYPE ki_ana_chat_answers_without_sources_total counter")
        for (intent,), count in sorted(_chat_answers_without_sources_total.items()):
            i = _escape_label(intent)
            lines.append(f"ki_ana_chat_answers_without_sources_total{{intent=\"{i}\"}} {int(count)}")

        lines.append("# HELP ki_ana_chat_answer_duration_seconds Chat answer duration histogram (best-effort, app-level)")
        lines.append("# TYPE ki_ana_chat_answer_duration_seconds histogram")
        for (intent, le), count in sorted(_chat_answer_duration_seconds_bucket.items()):
            i = _escape_label(intent)
            le_label = "+Inf" if (isinstance(le, float) and math.isinf(le)) else ("{:.3f}".format(float(le)).rstrip("0").rstrip("."))
            lines.append(f"ki_ana_chat_answer_duration_seconds_bucket{{intent=\"{i}\",le=\"{le_label}\"}} {int(count)}")
        for (intent,), total in sorted(_chat_answer_duration_seconds_sum.items()):
            i = _escape_label(intent)
            lines.append(f"ki_ana_chat_answer_duration_seconds_sum{{intent=\"{i}\"}} {float(total):.6f}")
        for (intent,), cnt in sorted(_chat_answer_duration_seconds_count.items()):
            i = _escape_label(intent)
            lines.append(f"ki_ana_chat_answer_duration_seconds_count{{intent=\"{i}\"}} {int(cnt)}")

        lines.append("# HELP ki_ana_quality_gate_total Quality gate hits (observed vs enforced)")
        lines.append("# TYPE ki_ana_quality_gate_total counter")
        # Always export known label combinations (0 if never incremented)
        for gate in _KNOWN_QUALITY_GATES:
            for mode in _KNOWN_QUALITY_GATE_MODES:
                count = _quality_gate_total.get((gate, mode), 0)
                g = _escape_label(gate)
                m = _escape_label(mode)
                lines.append(f"ki_ana_quality_gate_total{{gate=\"{g}\",mode=\"{m}\"}} {int(count)}")

        # Also export any dynamic/unknown gates that were observed
        for (gate, mode), count in sorted(_quality_gate_total.items()):
            if gate in _KNOWN_QUALITY_GATES and mode in _KNOWN_QUALITY_GATE_MODES:
                continue
            g = _escape_label(gate)
            m = _escape_label(mode)
            lines.append(f"ki_ana_quality_gate_total{{gate=\"{g}\",mode=\"{m}\"}} {int(count)}")

    # External gauges (outside lock)
    try:
        with _external_cache_lock:
            ext = dict(_external_cache)

        # ---- Celery task SLIs -------------------------------------------------
        lines.append("# HELP ki_ana_celery_task_total Total Celery task outcomes")
        lines.append("# TYPE ki_ana_celery_task_total counter")
        task_total = ext.get("celery_task_total")
        if isinstance(task_total, dict):
            for k, v in sorted(task_total.items(), key=lambda kv: str(kv[0])):
                try:
                    key = str(k)
                    task, status = key.split("|", 1)
                    cnt = int(float(v))
                except Exception:
                    continue
                lines.append(
                    f"ki_ana_celery_task_total{{task=\"{_escape_label(task)}\",status=\"{_escape_label(status)}\"}} {cnt}"
                )

        lines.append("# HELP ki_ana_celery_task_retries_total Total Celery task retries")
        lines.append("# TYPE ki_ana_celery_task_retries_total counter")
        retries = ext.get("celery_task_retries_total")
        if isinstance(retries, dict):
            for task, v in sorted(retries.items(), key=lambda kv: str(kv[0])):
                try:
                    cnt = int(float(v))
                except Exception:
                    continue
                lines.append(f"ki_ana_celery_task_retries_total{{task=\"{_escape_label(str(task))}\"}} {cnt}")

        lines.append("# HELP ki_ana_celery_task_inflight In-flight Celery tasks (best-effort)")
        lines.append("# TYPE ki_ana_celery_task_inflight gauge")
        inflight = ext.get("celery_task_inflight")
        if isinstance(inflight, dict):
            for task, v in sorted(inflight.items(), key=lambda kv: str(kv[0])):
                try:
                    g = int(float(v))
                except Exception:
                    continue
                lines.append(f"ki_ana_celery_task_inflight{{task=\"{_escape_label(str(task))}\"}} {g}")

        lines.append("# HELP ki_ana_celery_agg_last_update_seconds Unix timestamp of last Celery task aggregate update")
        lines.append("# TYPE ki_ana_celery_agg_last_update_seconds gauge")
        last_update = ext.get("celery_agg_last_update_ts")
        if isinstance(last_update, dict):
            for task, v in sorted(last_update.items(), key=lambda kv: str(kv[0])):
                try:
                    ts = int(float(v))
                except Exception:
                    continue
                lines.append(f"ki_ana_celery_agg_last_update_seconds{{task=\"{_escape_label(str(task))}\"}} {ts}")

        lines.append("# HELP ki_ana_celery_task_runtime_seconds Celery task runtime histogram")
        lines.append("# TYPE ki_ana_celery_task_runtime_seconds histogram")
        runtime_bucket = ext.get("celery_task_runtime_bucket")
        runtime_sum = ext.get("celery_task_runtime_sum")
        runtime_count = ext.get("celery_task_runtime_count")

        if isinstance(runtime_bucket, dict):
            buckets_by_task: Dict[str, Dict[str, int]] = {}
            for k, v in runtime_bucket.items():
                try:
                    key = str(k)
                    task, le = key.split("|", 1)
                    cnt = int(float(v))
                except Exception:
                    continue
                buckets_by_task.setdefault(task, {})[le] = buckets_by_task.setdefault(task, {}).get(le, 0) + cnt

            def _le_sort_key(le: str) -> float:
                try:
                    if le == "+Inf":
                        return float("inf")
                    return float(le)
                except Exception:
                    return float("inf")

            for task, per_le in sorted(buckets_by_task.items(), key=lambda kv: kv[0]):
                running = 0
                for le in sorted(per_le.keys(), key=_le_sort_key):
                    if le == "+Inf":
                        continue
                    running += int(per_le.get(le, 0) or 0)
                    lines.append(
                        f"ki_ana_celery_task_runtime_seconds_bucket{{task=\"{_escape_label(task)}\",le=\"{_escape_label(le)}\"}} {running}"
                    )
                total = running + int(per_le.get("+Inf", 0) or 0)
                lines.append(
                    f"ki_ana_celery_task_runtime_seconds_bucket{{task=\"{_escape_label(task)}\",le=\"+Inf\"}} {total}"
                )

        if isinstance(runtime_sum, dict):
            for task, v in sorted(runtime_sum.items(), key=lambda kv: str(kv[0])):
                try:
                    s = float(v)
                except Exception:
                    continue
                lines.append(f"ki_ana_celery_task_runtime_seconds_sum{{task=\"{_escape_label(str(task))}\"}} {s:.6f}")

        if isinstance(runtime_count, dict):
            for task, v in sorted(runtime_count.items(), key=lambda kv: str(kv[0])):
                try:
                    c = int(float(v))
                except Exception:
                    continue
                lines.append(f"ki_ana_celery_task_runtime_seconds_count{{task=\"{_escape_label(str(task))}\"}} {c}")

        lines.append("# HELP ki_ana_dependency_up 1 if dependency is reachable (best-effort)")
        lines.append("# TYPE ki_ana_dependency_up gauge")
        for dep in ("redis", "qdrant", "minio"):
            v = ext.get(f"dependency_{dep}_up")
            if isinstance(v, int):
                lines.append(f"ki_ana_dependency_up{{dependency=\"{dep}\"}} {int(v)}")
            else:
                lines.append(f"ki_ana_dependency_up{{dependency=\"{dep}\"}} NaN")

        lines.append("# HELP ki_ana_celery_worker_up 1 if worker heartbeat is fresh")
        lines.append("# TYPE ki_ana_celery_worker_up gauge")
        v = ext.get("celery_worker_up")
        lines.append(f"ki_ana_celery_worker_up {int(v) if isinstance(v, int) else 0}")

        lines.append("# HELP ki_ana_celery_worker_heartbeat_age_seconds Age of last worker heartbeat")
        lines.append("# TYPE ki_ana_celery_worker_heartbeat_age_seconds gauge")
        age = ext.get("celery_worker_heartbeat_age_seconds")
        if isinstance(age, (int, float)):
            lines.append(f"ki_ana_celery_worker_heartbeat_age_seconds {float(age):.3f}")
        else:
            lines.append("ki_ana_celery_worker_heartbeat_age_seconds NaN")

        lines.append("# HELP ki_ana_celery_queue_backlog Number of pending tasks in default queue (best-effort)")
        lines.append("# TYPE ki_ana_celery_queue_backlog gauge")
        qb = ext.get("celery_queue_backlog")
        if isinstance(qb, int):
            lines.append(f"ki_ana_celery_queue_backlog {int(qb)}")
        else:
            lines.append("ki_ana_celery_queue_backlog NaN")
    except Exception:
        pass

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
