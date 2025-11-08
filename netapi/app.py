from __future__ import annotations
# Ensure database schema is present early
try:
    from .db import init_db, ensure_columns, ensure_knowledge_indexes
    init_db()
    ensure_columns()
    ensure_knowledge_indexes()
    print("✅ Database initialized (tables ensured)")
    # Seed default users (idempotent)
    try:
        from .db_seed import seed_users as _seed_users
        _seed_users()
        print("✅ Seed users ensured")
    except Exception as _e_seed:
        try:
            print(f"⚠️  Seed users skipped: {_e_seed}")
        except Exception:
            pass
except Exception as _e_db_init:
    try:
        print(f"❌ Database init failed: {_e_db_init}")
    except Exception:
        pass
# netapi/app.py
from fastapi import FastAPI, Request, Depends, HTTPException
import os
import time
import json
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
# Optional Starlette middlewares (be tolerant to older Starlette versions)
try:
    from starlette.middleware.gzip import GZipMiddleware  # type: ignore
except Exception:  # pragma: no cover
    GZipMiddleware = None  # type: ignore
try:
    from starlette.middleware.proxy_headers import ProxyHeadersMiddleware  # type: ignore
except Exception:  # pragma: no cover
    ProxyHeadersMiddleware = None  # type: ignore

from .config import settings, STATIC_DIR
from .brain import brain_status
from .deps import get_current_user_required, has_any_role

# Routers are imported lazily and guarded, so a missing optional
# dependency (e.g., sse_starlette) doesn't crash the whole app.
try:
    from netapi.modules.auth.router import router as auth_router
except Exception:
    auth_router = None  # type: ignore
try:
    from netapi.modules.chat.router import router as chat_router
except Exception as _e_chat_router:
    chat_router = None  # type: ignore
    try:
        print("❌ Chat router failed to load:", _e_chat_router)
    except Exception:
        pass
try:
    from netapi.modules.chat.folders_router import router as folders_router
except Exception as _e_folders_router:
    folders_router = None  # type: ignore
    try:
        print("❌ Folders router failed to load:", _e_folders_router)
    except Exception:
        pass
try:
    from netapi.modules.addressbook import router as addressbook_router
except Exception as _e_addressbook_router:
    addressbook_router = None  # type: ignore
    try:
        print("❌ Addressbook router failed to load:", _e_addressbook_router)
    except Exception:
        pass
try:
    from netapi.modules.audit import router as audit_router
except Exception as _e_audit_router:
    audit_router = None  # type: ignore
    try:
        print("❌ Audit router failed to load:", _e_audit_router)
    except Exception:
        pass
try:
    from netapi.modules.emotion import router as emotion_router
except Exception as _e_emotion_router:
    emotion_router = None  # type: ignore
    try:
        print("❌ Emotion router failed to load:", _e_emotion_router)
    except Exception:
        pass
try:
    from netapi.modules.timeflow.router import router as timeflow_router
except Exception as _e_timeflow_router:
    timeflow_router = None  # type: ignore
    try:
        print("❌ TimeFlow router failed to load:", _e_timeflow_router)
    except Exception:
        pass
try:
    from netapi.modules.autopilot.router import router as autopilot_router
except Exception:
    autopilot_router = None  # type: ignore
try:
    from netapi.modules.pages.router import router as pages_router
except Exception:
    pages_router = None  # type: ignore
try:
    from netapi.modules.memory.router import router as memory_router
except Exception:
    memory_router = None  # type: ignore
try:
    from netapi.modules.web.router import router as web_router
except Exception:
    web_router = None  # type: ignore
try:
    from netapi.modules.viewer.router import router as viewer_router
except Exception:
    viewer_router = None  # type: ignore
try:
    from netapi.modules.os.router import router as os_router
except Exception:
    os_router = None  # type: ignore
try:
    from netapi.modules.kernel.router import router as kernel_router
except Exception:
    kernel_router = None  # type: ignore
try:
    from netapi.modules.subminds.router import router as subminds_router
except Exception:
    subminds_router = None  # type: ignore
try:
    from netapi.modules.guardian.router import router as guardian_router
except Exception:
    guardian_router = None  # type: ignore
try:
    from netapi.modules.billing.router import router as billing_router
except Exception:
    billing_router = None  # type: ignore
try:
    from netapi.modules.media.router import router as media_router
except Exception:
    media_router = None  # type: ignore
try:
    from netapi.modules.voice.router import router as voice_router
except Exception:
    voice_router = None  # type: ignore
try:
    from netapi.modules.stt.router import router as stt_router
except Exception:
    stt_router = None  # type: ignore
try:
    from netapi.modules.ingest.router import router as ingest_router
except Exception:
    ingest_router = None  # type: ignore
try:
    from netapi.modules.agent.router import router as agent_router
except Exception:
    agent_router = None  # type: ignore
try:
    from netapi.modules.devices.router import router as devices_router
except Exception:
    devices_router = None  # type: ignore
try:
    from netapi.modules.stats.router import router as stats_router
except Exception:
    stats_router = None  # type: ignore
try:
    from netapi.modules.colearn.router import router as colearn_router
except Exception:
    colearn_router = None  # type: ignore
try:
    from netapi.modules.genesis.router import router as genesis_router
except Exception:
    genesis_router = None  # type: ignore
try:
    from netapi.modules.feedback.router import router as feedback_router
except Exception:
    feedback_router = None  # type: ignore
try:
    from netapi.modules.subki.router import router as subki_router
except Exception:
    subki_router = None  # type: ignore
try:
    from netapi.modules.self.router import router as self_router
except Exception:
    self_router = None  # type: ignore
try:
    from netapi.modules.dashboard_mock.router import router as dashboard_mock_router
except Exception:
    dashboard_mock_router = None  # type: ignore
try:
    from netapi.modules.blocks.router import router as blocks_router
except Exception:
    blocks_router = None  # type: ignore
try:
    from netapi.modules.events.router import router as events_router
except Exception:
    events_router = None  # type: ignore
try:
    from netapi.modules.reflection.router import router as reflection_router
except Exception:
    reflection_router = None  # type: ignore
try:
    from netapi.modules.plan.router import router as plan_router
except Exception:
    plan_router = None  # type: ignore
try:
    from netapi.modules.persona.router import router as persona_router
except Exception:
    persona_router = None  # type: ignore
try:
    from netapi.modules.knowledge.router import router as knowledge_router
except Exception:
    knowledge_router = None  # type: ignore
try:
    from netapi.modules.ethics.router import router as ethics_router
except Exception:
    ethics_router = None  # type: ignore
try:
    from netapi.modules.crawler.router import router as crawler_router
except Exception as _e_crawler_router:
    crawler_router = None  # type: ignore
    try:
        print(f"❌ Import crawler_router failed: {_e_crawler_router}")
    except Exception:
        pass
try:
    from netapi.modules.crawler.router import ui_router as crawler_ui_router
except Exception as _e_crawler_ui_router:
    crawler_ui_router = None  # type: ignore
    try:
        print(f"❌ Import crawler_ui_router failed: {_e_crawler_ui_router}")
    except Exception:
        pass
try:
    from netapi.modules.export.router import router as export_router
except Exception:
    export_router = None  # type: ignore
try:
    from netapi.modules.settings.router import router as settings_router
except Exception as _e_settings_router:
    settings_router = None  # type: ignore
    try:
        print(f"❌ Import settings_router failed: {_e_settings_router}")
    except Exception:
        pass
try:
    from netapi.modules.logs.router import router as logs_router
except Exception:
    logs_router = None  # type: ignore
try:
    from netapi.modules.admin.router import router as admin_router
except Exception:
    admin_router = None  # type: ignore
try:
    from netapi.modules.telemetry.router import router as telemetry_router
except Exception:
    telemetry_router = None  # type: ignore
try:
    from netapi.modules.jobs.router import router as jobs_router
except Exception:
    jobs_router = None  # type: ignore
try:
    from netapi.modules.autonomy.router import router as autonomy_router
except Exception:
    autonomy_router = None  # type: ignore
try:
    from netapi.modules.insight.router import router as insight_router
except Exception:
    insight_router = None  # type: ignore
try:
    from netapi.modules.goals.router import router as goals_router
except Exception:
    goals_router = None  # type: ignore
AutonomyManager = None
if os.getenv("KI_ENABLE_AUTONOMY", "0").strip() in {"1", "true", "True"}:
    try:
        # Autonomy background loops (self-reflection, knowledge updates)
        from importlib.machinery import SourceFileLoader as _Loader
        _autonomy_mod = _Loader("autonomy", str(Path.home() / "ki_ana" / "system" / "autonomy.py")).load_module()  # type: ignore
        AutonomyManager = getattr(_autonomy_mod, "AutonomyManager", None)
    except Exception:
        AutonomyManager = None
# Kernel (optional). Provide a no-op fallback so API can start without kernel package.
try:
    from netapi.modules.kernel.core import KERNEL  # type: ignore
except Exception:
    class _NoOpKernel:
        async def start(self):
            return None
        async def stop(self):
            return None
    KERNEL = _NoOpKernel()  # type: ignore

import asyncio

# Allow configuring a root_path when sitting behind a reverse proxy
# Treat "/" as unset to avoid breaking routing (Starlette strips root_path prefix)
RAW_ROOT_PATH = getattr(settings, "ROOT_PATH", "") or ""
ROOT_PATH = (RAW_ROOT_PATH or "").strip()
if ROOT_PATH == "/":
    ROOT_PATH = ""

app = FastAPI(title="KI_ana API", version="1.0", debug=settings.DEBUG, root_path=ROOT_PATH)

# ---- Kernel lifecycle only here (avoid double start/stop elsewhere) --------
@app.on_event("startup")
async def _kernel_boot() -> None:
    async def _safe_start():
        try:
            # Don't block startup; keep a short timeout so nginx won't 504 on / during cold start
            await asyncio.wait_for(KERNEL.start(), timeout=3.0)
        except Exception:
            # Kernel will retry tasks internally; API should still come up
            pass
    asyncio.create_task(_safe_start())

    # Install logging broadcaster so /api/logs endpoints work
    try:
        from .logging_bridge import BROADCASTER
        BROADCASTER.install()
    except Exception:
        pass

    # Load genesis context in background
    async def _load_genesis_ctx():
        try:
            from importlib.machinery import SourceFileLoader as _Loader
            _p = Path.home() / "ki_ana" / "system" / "startup_tasks.py"
            _mod = _Loader("startup_tasks", str(_p)).load_module()  # type: ignore
            ctx = _mod.load_genesis_context()  # type: ignore
            setattr(app.state, "genesis_context", ctx)
        except Exception:
            setattr(app.state, "genesis_context", {"emergency_present": None, "cognitive_present": None})
    asyncio.create_task(_load_genesis_ctx())


@app.on_event("shutdown")
async def _kernel_down() -> None:
    try:
        await asyncio.wait_for(KERNEL.stop(), timeout=3.0)
    except BaseException:
        pass

# ---- Middlewares -----------------------------------------------------------
# Respect X-Forwarded-* headers set by nginx / reverse proxy (if available)
if ProxyHeadersMiddleware is not None:
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Compress larger responses (HTML/JS/CSS) if middleware exists
if GZipMiddleware is not None:
    app.add_middleware(GZipMiddleware, minimum_size=512)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(settings, "CORS_ORIGINS", [
        "https://ki-ana.at",
        "https://www.ki-ana.at",
        "http://localhost",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:8000",
    ]),
    # Allow all ki-ana.at subdomains (e.g., app., beta., etc.)
    allow_origin_regex=getattr(
        settings,
        "CORS_ORIGIN_REGEX",
        r"https://([a-z0-9\-]+\.)?ki-ana\.at"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware (ensures headers are present even if nginx doesn't add them in all locations)
@app.middleware("http")
async def _security_headers(request: Request, call_next):
    resp = await call_next(request)
    try:
        # Only emit HSTS when served over HTTPS (respect proxy headers)
        scheme = (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").lower()
        if scheme == "https":
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        # Auto-upgrade any stray http:// requests in the page
        # Note: This is safe to send on all responses
        resp.headers["Content-Security-Policy"] = "upgrade-insecure-requests"
        # Hardening
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    except Exception:
        # Be permissive: never block a response due to header errors
        pass
    return resp

# ---- Static ---------------------------------------------------------------
# Mount /static only if directory exists (avoid startup crash)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    # Mount /uploads (user media)
    try:
        from pathlib import Path as _Path
        _KI_ROOT = _Path(os.getenv("KI_ROOT", str(_Path.home() / "ki_ana")))
        _UP = _KI_ROOT / "uploads"
        if _UP.exists():
            app.mount("/uploads", StaticFiles(directory=str(_UP)), name="uploads")
    except Exception:
        pass

# ---- Health & diagnostics --------------------------------------------------
@app.get("/health", include_in_schema=False)
def health():
    # Extremely lightweight and never touches the kernel
    return {"ok": True}

# Very fast liveness ping used by reverse proxies (no JSON parsing needed)
@app.get("/_/ping", include_in_schema=False)
def ping():
    return JSONResponse({"ok": True})

@app.get("/api/metrics", include_in_schema=False)
def api_metrics():
    """Lightweight readiness/metrics endpoint for frontend preflight checks.
    Currently exposes Ollama (local LLM) availability and configured host/model.
    """
    ollama = {"available": False}
    try:
        from .core import llm_local as _llm  # type: ignore
        try:
            avail = bool(getattr(_llm, "available", lambda: False)())
        except Exception:
            avail = False
        host = getattr(_llm, "OLLAMA_HOST", None)
        model = getattr(_llm, "OLLAMA_MODEL", None)
        model_present = None
        model_running = None
        # Probe model presence via Ollama tags and running state via ps (best-effort)
        try:
            import requests as _rq  # type: ignore
            if host:
                try:
                    rt = _rq.get(f"{host}/api/tags", timeout=2)
                    if rt.ok:
                        jd = rt.json() or {}
                        arr = jd.get("models") or []
                        model_present = any((m.get("name") == model) for m in arr)
                except Exception:
                    model_present = None
                try:
                    rp = _rq.get(f"{host}/api/ps", timeout=2)
                    if rp.ok:
                        jd2 = rp.json() or {}
                        arr2 = jd2.get("models") or []
                        model_running = any((m.get("model") == model) or (m.get("name") == model) for m in arr2)
                except Exception:
                    model_running = None
        except Exception:
            pass
        ollama = {
            "available": avail,
            "host": host,
            "model": model,
            "model_present": model_present,
            "model_running": model_running,
        }
    except Exception:
        # keep defaults; endpoint should never raise
        pass
    return {"ok": True, "ollama": ollama}

# Unified system status for UI (resources + metrics)
@app.get("/api/system/status", include_in_schema=False)
def api_system_status():
    # Resources (best-effort)
    resources = {}
    try:
        import psutil  # type: ignore
        try:
            resources["cpu_percent"] = float(psutil.cpu_percent(interval=None))
        except Exception:
            resources["cpu_percent"] = None
        try:
            resources["cpu_count"] = int(psutil.cpu_count(logical=True) or 0)
        except Exception:
            resources["cpu_count"] = None
        try:
            la = os.getloadavg()  # type: ignore
            resources["loadavg"] = {"1m": float(la[0]), "5m": float(la[1]), "15m": float(la[2])}
        except Exception:
            resources["loadavg"] = None
        try:
            vm = psutil.virtual_memory()
            resources["memory"] = {"total": int(vm.total), "used": int(vm.used), "percent": float(vm.percent)}
        except Exception:
            resources["memory"] = None
        try:
            du = psutil.disk_usage("/")
            resources["disk"] = {"total": int(du.total), "used": int(du.used), "percent": float(du.percent)}
        except Exception:
            resources["disk"] = None
        try:
            nio = psutil.net_io_counters()
            resources["net_io"] = {"bytes_sent": int(nio.bytes_sent), "bytes_recv": int(nio.bytes_recv)}
        except Exception:
            resources["net_io"] = None
        # Processes quick count
        try:
            resources["procs"] = {"count": len(psutil.pids())}
        except Exception:
            resources["procs"] = None
    except Exception:
        resources = {}

    # Metrics (reuse api_metrics logic)
    try:
        m = api_metrics()
        ollama = m.get("ollama", {}) if isinstance(m, dict) else {}
    except Exception:
        ollama = {"available": False}

    # Emergency sentinel check
    try:
        from pathlib import Path as _P
        _KI_ROOT = _P(os.getenv("KI_ROOT", str(_P.home() / "ki_ana")))
        emergency_active = (_KI_ROOT / "emergency_stop").exists()
    except Exception:
        emergency_active = False

    # Jobs and planner quick health (best-effort)
    jobs_count = None
    plan_queued = None
    step_queued = None
    worker_heartbeat_age = None
    autonomy_level = None
    devices_offline = None
    devices_total = None
    anomalies: list[str] = []
    try:
        from .db import SessionLocal
        from .models import Job, Device
        from .modules.plan.models import Plan, PlanStep  # type: ignore
    except Exception:
        Job = None  # type: ignore
        Device = None  # type: ignore
        Plan = None  # type: ignore
        PlanStep = None  # type: ignore
    try:
        from pathlib import Path as _P
        _KI_ROOT = _P(os.getenv("KI_ROOT", str(_P.home() / "ki_ana")))
        hb = _KI_ROOT / "runtime" / "plan_worker_heartbeat"
        if hb.exists():
            try:
                t = int((hb.read_text(encoding="utf-8").strip() or "0"))
                worker_heartbeat_age = max(0, int(time.time()) - t)
            except Exception:
                worker_heartbeat_age = None
        # Autonomy level (best-effort from runtime settings)
        cfg = _KI_ROOT / "runtime" / "autonomy.json"
        if cfg.exists():
            try:
                import json as _json
                autonomy_level = int((_json.loads(cfg.read_text(encoding="utf-8")) or {}).get("level", 0))
            except Exception:
                autonomy_level = None
    except Exception:
        pass
    try:
        if Job is not None:
            with SessionLocal() as db:
                jobs_count = db.query(Job).count()
                if Plan is not None:
                    plan_queued = db.query(Plan).filter(Plan.status == "queued").count()
                if PlanStep is not None:
                    step_queued = db.query(PlanStep).filter(PlanStep.status == "queued").count()
                if Device is not None:
                    try:
                        devices_total = db.query(Device).count()
                    except Exception:
                        devices_total = None
                    try:
                        nowi = int(time.time())
                        TH = int(os.getenv("DEVICE_OFFLINE_SEC", "600"))
                        # Count devices where status==offline OR last_seen older than threshold
                        offline_by_status = db.query(Device).filter(Device.status == "offline").count()
                        offline_by_seen = db.query(Device).filter(Device.last_seen > 0, (nowi - Device.last_seen) > TH).count()
                        devices_offline = int(offline_by_status or 0) + int(offline_by_seen or 0)
                    except Exception:
                        devices_offline = None
    except Exception:
        pass

    # Simple anomaly detection thresholds
    try:
        if worker_heartbeat_age is not None and worker_heartbeat_age > 120:
            anomalies.append("worker_heartbeat_stale")
        if (step_queued or 0) > 500:
            anomalies.append("planner_steps_backlog")
        if (jobs_count or 0) > 1000:
            anomalies.append("jobs_backlog")
        if (devices_offline or 0) > 0:
            anomalies.append("devices_offline")
    except Exception:
        pass

    # Best-effort anomaly logging to audit/knowledge (rate-limited via a touch file)
    try:
        if anomalies:
            from pathlib import Path as _P
            _KI_ROOT = _P(os.getenv("KI_ROOT", str(_P.home() / "ki_ana")))
            stamp = _KI_ROOT / "runtime" / "self_health_last_log"
            now = int(time.time())
            last = 0
            try:
                last = int((stamp.read_text(encoding="utf-8").strip() or "0"))
            except Exception:
                last = 0
            if now - last > 300:  # log at most every 5 min
                try:
                    stamp.parent.mkdir(parents=True, exist_ok=True)
                    stamp.write_text(str(now), encoding="utf-8")
                except Exception:
                    pass
                # Audit
                try:
                    from .modules.plan.router import write_audit  # type: ignore
                    write_audit("self_health_anomaly", actor_id=0, target_type="system", target_id=0, meta={"anomalies": anomalies})
                except Exception:
                    pass
                # Knowledge
                try:
                    import requests as _rq  # type: ignore
                    admin_tok = os.getenv("ADMIN_API_TOKEN", "").strip()
                    headers = {"Content-Type": "application/json"}
                    if admin_tok:
                        headers["Authorization"] = f"Bearer {admin_tok}"
                    _rq.post(str(request.base_url).rstrip("/") + "/api/knowledge", json={
                        "source": "self-health", "type": "note", "tags": "self,health,anomaly",
                        "content": f"Anomalies detected: {', '.join(anomalies)}",
                    }, headers=headers, timeout=2)
                except Exception:
                    pass
    except Exception:
        pass

    metrics = {
        "ollama": ollama,
        "emergency_active": emergency_active,
        "jobs": jobs_count,
        "plan_steps_queued": step_queued,
        "plans_queued": plan_queued,
        "worker_heartbeat_age": worker_heartbeat_age,
        "autonomy_level": autonomy_level,
        "devices_offline": devices_offline,
        "devices_total": devices_total,
        "anomalies": anomalies,
    }
    # Add planner safety-valve counters from runtime/stats.json (best-effort)
    try:
        from pathlib import Path as _P
        _KI_ROOT = _P(os.getenv("KI_ROOT", str(_P.home() / "ki_ana")))
        stats_p = _KI_ROOT / "runtime" / "stats.json"
        if stats_p.exists():
            try:
                import json as _json
                sj = _json.loads(stats_p.read_text(encoding="utf-8") or "{}")
                metrics["planner_safety_valve_count"] = int(sj.get("planner_safety_valve_count") or 0)
                if sj.get("last_safety_valve_topic"):
                    metrics["last_safety_valve_topic"] = str(sj.get("last_safety_valve_topic") or "")
            except Exception:
                pass
    except Exception:
        pass
    return {"ts": int(time.time()), "metrics": metrics, "resources": resources}

# Lightweight config endpoint for frontend feature flags/URLs
@app.get("/api/system/config", include_in_schema=False)
def api_system_config():
    try:
        upgrade_url = os.getenv("KI_UPGRADE_URL", "/static/upgrade.html").strip() or "/static/upgrade.html"
    except Exception:
        upgrade_url = "/static/upgrade.html"
    try:
        free_q = int(os.getenv("FREE_DAILY_QUOTA", "20"))
    except Exception:
        free_q = 20
    try:
        guardian_auto = str(os.getenv("GUARDIAN_AUTO_SUGGEST", "0")).strip() in {"1","true","True"}
    except Exception:
        guardian_auto = False
    return {"ok": True, "upgrade_url": upgrade_url, "free_daily_quota": free_q, "guardian_auto_suggest": guardian_auto}

# Vision endpoint: serve KI_ana Vision principles
@app.get("/api/system/vision", include_in_schema=False)
def api_system_vision():
    try:
        from pathlib import Path as _P
        _KI_ROOT = _P(os.getenv("KI_ROOT", str(_P.home() / "ki_ana")))
        vision_path = _KI_ROOT / "netapi" / "config" / "vision.json"
        if vision_path.exists():
            try:
                import json as _json
                data = _json.loads(vision_path.read_text(encoding="utf-8") or "{}")
                # minimal validation
                name = data.get("name") or "KI_ana Vision"
                principles = list(data.get("principles") or [])
                owner = data.get("owner") or "Papa"
                ver = int(data.get("version") or 1)
                return {"ok": True, "vision": {"name": name, "principles": principles, "owner": owner, "version": ver}}
            except Exception:
                pass
        # default fallback
        return {"ok": True, "vision": {"name": "KI_ana Vision", "principles": [
            "Sei transparent über Quellen (origin).",
            "Speichere jede Antwort als Block im Memory.",
            "Vergleiche neue Erkenntnisse mit bestehendem Wissen.",
            "Wachse und verbessere dich kontinuierlich.",
            "Liefere dem User immer die bestmögliche, aktuelle Antwort."
        ], "owner": "Papa", "version": 1}}
    except Exception:
        return {"ok": True, "vision": {"name": "KI_ana Vision", "principles": [], "owner": "Papa", "version": 1}}

# Update vision (admin/creator/papa only)
@app.post("/api/system/vision", include_in_schema=False)
def api_system_vision_update(payload: dict, current=Depends(get_current_user_required)):
    try:
        if not has_any_role(current, {"admin","creator","papa"}):
            raise HTTPException(status_code=403, detail="forbidden")
        from pathlib import Path as _P
        import json as _json
        _KI_ROOT = _P(os.getenv("KI_ROOT", str(_P.home() / "ki_ana")))
        vision_path = _KI_ROOT / "netapi" / "config" / "vision.json"
        # Load existing to compute version bump
        old = {}
        try:
            if vision_path.exists():
                old = _json.loads(vision_path.read_text(encoding="utf-8") or "{}")
        except Exception:
            old = {}
        name = str(payload.get("name") or old.get("name") or "KI_ana Vision")
        owner = str(payload.get("owner") or old.get("owner") or "Papa")
        principles = payload.get("principles")
        if not isinstance(principles, list):
            raise HTTPException(400, detail="principles must be an array")
        ver = int((old.get("version") or 0)) + 1
        data = {"name": name, "owner": owner, "principles": principles, "version": ver}
        vision_path.parent.mkdir(parents=True, exist_ok=True)
        vision_path.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "vision": data}
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": "vision_update_failed", "detail": str(e)[:300]})

# Dedicated LLM status endpoint
@app.get("/api/llm/status", include_in_schema=False)
def api_llm_status():
    status_file = os.getenv("KIANA_STATUS_FILE", "./runtime/llm_status.json")
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        # ensure model field present from env as fallback
        if not data.get("model"):
            data["model"] = os.getenv("OLLAMA_MODEL", "")
        return data
    except Exception:
        return {"model": os.getenv("OLLAMA_MODEL", ""), "status": "loading", "message": "Initialisierung...", "ts": None}

@app.get("/api/brain/status")
def api_brain_status():
    st = brain_status()
    st.update({"autopilot_running": False})
    return {"ok": True, "status": st}

@app.get("/api/system/timeflow", include_in_schema=False)
def api_system_timeflow():
    """TimeFlow monitoring endpoint for activity tracking and system metrics."""
    try:
        import psutil  # type: ignore
        has_psutil = True
    except Exception:
        has_psutil = False
    
    # Calculate uptime
    uptime_seconds = 0
    try:
        if has_psutil and hasattr(psutil, 'boot_time'):
            uptime_seconds = int(time.time() - psutil.boot_time())
        else:
            try:
                with open('/proc/uptime','r') as f:
                    uptime_seconds = int(float(f.read().split()[0]))
            except Exception:
                pass
    except Exception:
        pass
    
    # Count active processes (simplified)
    active_count = 0
    try:
        if has_psutil:
            active_count = len([p for p in psutil.process_iter(['name']) if 'python' in p.info.get('name', '').lower() or 'uvicorn' in p.info.get('name', '').lower()])
        else:
            # Fallback: count running python processes
            import subprocess
            result = subprocess.run(['pgrep', '-c', 'python'], capture_output=True, text=True)
            if result.returncode == 0:
                active_count = int(result.stdout.strip() or 0)
    except Exception:
        active_count = 1  # At least this process
    
    # Activations today (mock data - could be pulled from logs/db)
    activations_today = 0
    try:
        from pathlib import Path as _P
        _KI_ROOT = _P(os.getenv("KI_ROOT", str(_P.home() / "ki_ana")))
        # Count blocks created today
        blocks_dir = _KI_ROOT / "memory" / "long_term" / "blocks"
        if blocks_dir.exists():
            import datetime
            today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            for block_file in blocks_dir.glob("*.json"):
                if block_file.stat().st_mtime >= today_start:
                    activations_today += 1
    except Exception:
        pass
    
    # Timeline events (last 10 significant events)
    timeline = []
    try:
        from pathlib import Path as _P
        _KI_ROOT = _P(os.getenv("KI_ROOT", str(_P.home() / "ki_ana")))
        
        # Add system start event
        timeline.append({
            "timestamp": int(time.time() - uptime_seconds) * 1000,
            "title": "System gestartet",
            "description": "KI_ana Backend initialisiert"
        })
        
        # Add recent chat events from logs if available
        logs_dir = _KI_ROOT / "logs"
        if logs_dir.exists():
            chat_log = logs_dir / "audit_chat.jsonl"
            if chat_log.exists():
                try:
                    lines = chat_log.read_text().strip().split('\n')
                    for line in lines[-5:]:  # Last 5 chat events
                        try:
                            import json as _json
                            event = _json.loads(line)
                            timeline.append({
                                "timestamp": int(event.get("ts", time.time()) * 1000),
                                "title": "Chat-Aktivität",
                                "description": f"Nutzer: {event.get('user', 'unbekannt')}"
                            })
                        except Exception:
                            pass
                except Exception:
                    pass
        
        # Sort by timestamp descending
        timeline.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        timeline = timeline[:10]  # Keep only last 10
        
    except Exception:
        pass
    
    return {
        "ok": True,
        "active_count": active_count,
        "uptime": uptime_seconds,
        "activations_today": activations_today,
        "status": "active",
        "timeline": timeline
    }

# ---- Root & icons ----------------------------------------------------------
@app.get("/", include_in_schema=False)
def root_index():
    path = STATIC_DIR / "index.html"
    if path.exists():
        return FileResponse(path)
    return JSONResponse({"ok": True, "msg": "KI_ana API Root"})

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    path = STATIC_DIR / "favicon.ico"
    return FileResponse(path) if path.exists() else JSONResponse({"ok": True})

@app.get("/apple-touch-icon.png", include_in_schema=False)
def apple_touch():
    path = STATIC_DIR / "apple-touch-icon.png"
    return FileResponse(path) if path.exists() else JSONResponse({"ok": True})

# ---- Routers ---------------------------------------------------------------
# Alle optionalen Router importieren (sind bereits im oberen Teil enthalten)
# Robuste Einbindung für Chat und Settings mit klaren Start‑Logs

# Chat router
try:
    if chat_router is None:
        raise RuntimeError("chat_router is None")
    app.include_router(chat_router)
    print("✅ Chat router ready")
except Exception as e:
    print("❌ Chat router failed:", e)

# Settings router
try:
    if settings_router is None:
        raise RuntimeError("settings_router is None")
    app.include_router(settings_router)
    print("✅ Settings router ready")
except Exception as e:
    print("❌ Settings router failed:", e)

# Auth router
try:
    if auth_router is None:
        raise RuntimeError("auth_router is None")
    # Router already defines prefix="/api"; do not add another prefix here
    app.include_router(auth_router)
    print("✅ Auth router ready")
except Exception as e:
    print("❌ Auth router failed:", e)


# Alle übrigen Router automatisch einbinden (ohne Chat/Settings doppelt zu laden)
router_list = [
    autopilot_router, pages_router, folders_router, addressbook_router, audit_router, emotion_router, timeflow_router,
    # memory_router handled explicitly with prefix later
    web_router, viewer_router, os_router,
    kernel_router, subminds_router, guardian_router, billing_router,
    media_router, voice_router, stt_router, ingest_router, agent_router,
    devices_router, stats_router, colearn_router, genesis_router,
    feedback_router, subki_router, self_router, dashboard_mock_router, blocks_router,
    events_router, reflection_router, persona_router, knowledge_router,
    ethics_router, crawler_router, crawler_ui_router, export_router,
    logs_router, telemetry_router, admin_router, insight_router, goals_router, jobs_router, plan_router, autonomy_router
]

for r in router_list:
    try:
        if r is not None:
            app.include_router(r)
    except Exception as e:
        print(f"❌ Fehler beim Einbinden eines Routers: {e}")

# Explicitly mount memory viewer router with desired prefix, after others
try:
    if memory_router is not None:
        app.include_router(memory_router, prefix="/api/memory/knowledge")
        print("✅ Memory router mounted at /api/memory/knowledge")
except Exception as e:
    print("❌ Memory router mount failed:", e)

# Fallback stub: keep console quiet if jobs module is unavailable
if jobs_router is None:
    @app.get("/api/jobs/heartbeats", include_in_schema=False)
    def _jobs_heartbeats_stub():
        return {"ok": True, "items": []}
# ---- Emergency guard (write blockade) --------------------------------------
@app.middleware("http")
async def _emergency_guard(request: Request, call_next):
    try:
        # Allow safe methods unconditionally
        SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
        GET_MUTATING_PATHS = {
            # SSE streams that can persist messages/history
            "/api/chat/stream",
            "/api/agent/stream",
        }
        if request.method in SAFE_METHODS:
            # Even for GET, block known mutating endpoints when emergency is active
            from urllib.parse import urlsplit as _us
            p = _us(str(request.url)).path
            # Fast path: if no stop file, proceed
            from pathlib import Path as _P
            _KI_ROOT = _P(os.getenv("KI_ROOT", str(_P.home() / "ki_ana")))
            _SENT = _KI_ROOT / "emergency_stop"
            if not _SENT.exists():
                return await call_next(request)
            if p not in GET_MUTATING_PATHS:
                return await call_next(request)
            # otherwise, fall through to block
        # If sentinel exists, block mutating methods
        from pathlib import Path as _P
        _KI_ROOT = _P(os.getenv("KI_ROOT", str(_P.home() / "ki_ana")))
        _SENT = _KI_ROOT / "emergency_stop"
        if _SENT.exists():
            # Optional: surface activation info
            info = {}
            try:
                import json as _json
                info = _json.loads(_SENT.read_text(encoding="utf-8"))
            except Exception:
                info = {"file": str(_SENT)}
            return JSONResponse({"ok": False, "error": "emergency_stop_active", "details": info}, status_code=503, headers={"Retry-After": "600"})
    except Exception:
        # Fail‑open on guard errors to not DOS ourselves
        pass
    return await call_next(request)
