from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from ...deps import get_current_user_required, require_admin_area

router = APIRouter(prefix="/api/ops", tags=["ops"])


def _redact_db_url(url: str | None) -> str | None:
    if not url:
        return None
    u = str(url)
    # redact user:pass@ or :pass@ segments
    u = re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", u)
    u = re.sub(r"password=([^&]+)", r"password=***", u, flags=re.IGNORECASE)
    return u


def _safe_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except Exception:
        return None


@router.get("/summary")
def ops_summary(user=Depends(get_current_user_required)) -> Dict[str, Any]:
    require_admin_area(user)

    now_ts = int(time.time())
    sha = (os.getenv("KIANA_BUILD_SHA") or os.getenv("BUILD_SHA") or "").strip() or None
    env_value = (os.getenv("KIANA_ENV") or os.getenv("ENV") or "dev").strip().lower() or "dev"

    # --- Metrics / rolling windows (best-effort, per-process) ---
    try:
        from netapi.modules.observability import metrics as _m
        uptime = _safe_float(_m.uptime_seconds())
        http_1m = _m.window_http_stats(window_seconds=60, exclude_statuses={401})
        chat_p = _m.route_latency_quantiles(route="/api/v2/chat", method="POST", window_seconds=3600, quantiles=(0.95,))
        login_p = _m.route_latency_quantiles(route="/api/login", method="POST", window_seconds=3600, quantiles=(0.95,))
        limits_total = int(_m.limits_exceeded_total())
    except Exception:
        uptime = None
        http_1m = {"window_seconds": 60, "requests_total": 0, "requests_per_min": 0.0, "2xx_rate": None, "5xx_rate": None}
        chat_p = {"p95": None}
        login_p = {"p95": None}
        limits_total = 0

    # --- DB check (latency + ok + redacted url) ---
    db_url = os.getenv("DATABASE_URL")
    db_info: Dict[str, Any] = {"ok": None, "url": _redact_db_url(db_url), "latency_ms": None}
    try:
        from sqlalchemy import text as _t
        from netapi.db import SessionLocal
        t0 = time.perf_counter()
        with SessionLocal() as db:
            db.execute(_t("SELECT 1"))
        db_info["ok"] = True
        db_info["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
    except Exception:
        db_info["ok"] = False

    # --- Redis check + worker heartbeat (heartbeat is produced by backend/worker container) ---
    redis_info: Dict[str, Any] = {"ok": None, "latency_ms": None}
    worker_info: Dict[str, Any] = {"ok": None, "last_seen_ts": None, "age_seconds": None}
    try:
        import redis as _redis  # type: ignore

        rh = (os.getenv("REDIS_HOST") or "redis").strip() or "redis"
        rp = int(os.getenv("REDIS_PORT") or "6379")
        t0 = time.perf_counter()
        r = _redis.Redis(host=rh, port=rp, socket_timeout=1, socket_connect_timeout=1, decode_responses=True)
        r.ping()
        redis_info["ok"] = True
        redis_info["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)

        try:
            raw = r.get("kiana:worker:heartbeat")
            ts = int(raw) if raw else 0
            worker_info["last_seen_ts"] = ts or None
            if ts:
                age = max(0, now_ts - ts)
                worker_info["age_seconds"] = age
                worker_info["ok"] = bool(age <= 20)
            else:
                worker_info["ok"] = False
        except Exception:
            worker_info["ok"] = None
    except Exception:
        redis_info["ok"] = False
        worker_info["ok"] = None

    # --- Qdrant check ---
    qdrant_info: Dict[str, Any] = {"ok": None, "latency_ms": None}
    try:
        import httpx

        qh = (os.getenv("QDRANT_HOST") or "qdrant").strip() or "qdrant"
        qp = int(os.getenv("QDRANT_PORT") or "6333")
        url = f"http://{qh}:{qp}/healthz"
        t0 = time.perf_counter()
        with httpx.Client(timeout=1.5) as c:
            resp = c.get(url)
        qdrant_info["ok"] = bool(resp.status_code == 200)
        qdrant_info["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
    except Exception:
        qdrant_info["ok"] = False

    # --- Learning counters (best-effort, in-memory) ---
    learning: Dict[str, Any] = {"pending_count": 0, "accepted_24h": 0, "denied_24h": 0, "last_candidate_ts": None}
    try:
        from netapi.learning.candidates import get_learning_candidate_store

        st = get_learning_candidate_store().stats()
        learning = {
            "pending_count": int(st.get("pending") or 0),
            "accepted_24h": int(st.get("accepted_24h") or 0),
            "denied_24h": int(st.get("denied_24h") or 0),
            "last_candidate_ts": int(st.get("last_candidate_ts") or 0) or None,
        }
    except Exception:
        pass

    # --- MetaMind snapshot (best-effort) ---
    metamind: Dict[str, Any] = {"interactions": None, "tool_success_rate": None, "warnings": []}
    try:
        from netapi.core.meta_mind import MetaMind

        state = MetaMind().evaluate_system_state()
        metamind = {
            "interactions": int(getattr(state, "total_interactions", 0) or 0),
            "tool_success_rate": _safe_float(getattr(state, "tool_success_rate", 0.0)),
            "warnings": list(getattr(state, "warnings", []) or []),
        }
    except Exception:
        pass

    # --- Health status (traffic + latency + dependencies) ---
    p95_chat = _safe_float(chat_p.get("p95"))
    five_xx_rate = _safe_float(http_1m.get("5xx_rate"))
    db_ok = db_info.get("ok") is True
    base_bad = (not db_ok) or (five_xx_rate is not None and five_xx_rate > 0.02) or (p95_chat is not None and p95_chat > 3.0)
    base_warn = (five_xx_rate is not None and five_xx_rate >= 0.005) or (p95_chat is not None and p95_chat >= 1.5)
    if base_bad:
        health = "bad"
    elif base_warn:
        health = "warn"
    else:
        health = "good"

    return {
        "ok": True,
        "now_ts": now_ts,
        "env": env_value,
        "build_sha": sha,
        "uptime_seconds": uptime,
        "db": db_info,
        "redis": redis_info,
        "qdrant": qdrant_info,
        "worker": worker_info,
        "http_1m": http_1m,
        "latency_p95_by_route": {
            "/api/v2/chat": p95_chat,
            "/api/login": _safe_float(login_p.get("p95")),
        },
        "limits_exceeded_total": limits_total,
        "health_status": health,
        "metamind": metamind,
        "learning": learning,
    }
