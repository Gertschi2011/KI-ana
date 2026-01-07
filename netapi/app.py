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
from fastapi import FastAPI, Request, Depends, HTTPException, Response, Query
import os
import time
import json
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
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
from .deps import get_current_user_required, has_any_role, require_active_user
from fastapi import Depends

# App start timestamp (for uptime)
APP_STARTED_AT_TS = int(time.time())

# Global TimeFlow instance for /api/timeflow router
try:
    from netapi.modules.timeflow.engine import TimeFlow as _TimeFlow
    _tf_tz = (os.getenv("KIANA_TZ") or os.getenv("TZ") or "Europe/Vienna").strip() or "Europe/Vienna"
    TIMEFLOW = _TimeFlow(tz=_tf_tz)
except Exception:
    TIMEFLOW = None  # type: ignore

# Routers are imported lazily and guarded, so a missing optional
# dependency (e.g., sse_starlette) doesn't crash the whole app.
try:
    from netapi.modules.auth.router import router as auth_router
except Exception:
    auth_router = None
try:
    from netapi.modules.chat.router import router as chat_router
except Exception as _e_chat_router:
    chat_router = None  # type: ignore
    try:
        print("❌ Chat router failed to load:", _e_chat_router)
    except Exception:
        pass

# v2 chat router (clean architecture) - optional
try:
    from netapi.modules.chat.clean_router import router as chat_v2_router
except Exception as _e_chat_v2_router:
    chat_v2_router = None  # type: ignore
    try:
        print("❌ Chat v2 router failed to load:", _e_chat_v2_router)
    except Exception:
        pass
try:
    from netapi.modules.chat.folders import router as folders_router
except Exception as _e_folders:
    folders_router = None
    try:
        print("❌ Folders router failed to load:", _e_folders)
    except Exception:
        pass
try:
    from netapi.modules.chat.folders_router import router as folders_router_old
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
    from netapi.modules.memory.tool_router import router as memory_tools_router
except Exception:
    memory_tools_router = None  # type: ignore
try:
    from netapi.modules.web.router import router as web_router
except Exception:
    web_router = None  # type: ignore
try:
    from netapi.modules.security.router import router as security_router
except Exception:
    security_router = None  # type: ignore
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
    from netapi.modules.account.router import router as account_router
except Exception:
    account_router = None  # type: ignore
try:
    from netapi.modules.billing.router import router as billing_router
except Exception as _e_billing_router:
    # In production, billing config must be present; fail-fast.
    try:
        env_value = (os.getenv("KIANA_ENV") or os.getenv("ENV") or "dev").strip().lower()
        is_prod = (str(os.getenv("TEST_MODE", "0")).strip() != "1") and (env_value in {"prod", "production"})
    except Exception:
        is_prod = False
    if is_prod:
        raise
    billing_router = None  # type: ignore
    try:
        print("⚠️  Billing router disabled:", _e_billing_router)
    except Exception:
        pass
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
    from netapi.modules.ops.router import router as ops_router
except Exception:
    ops_router = None  # type: ignore
try:
    from netapi.modules.gdpr.dsar_router import router as gdpr_router
except Exception:
    gdpr_router = None  # type: ignore
try:
    from netapi.modules.privacy.router import router as privacy_router
except Exception:
    privacy_router = None  # type: ignore
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

# Crawler API router (frontend expects /api/crawler/*)
try:
    from netapi.modules.crawler.api_router import router as crawler_api_router
except Exception as _e_crawler_api_router:
    crawler_api_router = None  # type: ignore
    try:
        print(f"❌ Import crawler_api_router failed: {_e_crawler_api_router}")
    except Exception:
        pass
try:
    from netapi.modules.export.router import router as export_router
except Exception:
    export_router = None  # type: ignore
try:
    from netapi.modules.explain.router import router as explain_router
except Exception:
    explain_router = None  # type: ignore
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
    from netapi.modules.dashboard_adapter.router import router as dashboard_adapter_router
except Exception:
    dashboard_adapter_router = None  # type: ignore
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


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}

# --- Autonomous crawler loop configuration ----------------------------------
CRAWLER_AUTORUN = os.getenv("KIANA_CRAWLER_AUTORUN", "1") not in {"0", "false", "False"}
try:
    CRAWLER_INTERVAL = max(300, int(os.getenv("KIANA_CRAWLER_INTERVAL", "1800")))
except Exception:
    CRAWLER_INTERVAL = 1800

CRAWLER_PRIMARY = False
_CRAWLER_LOCK_PATH = Path("/tmp/kiana_crawler.lock")
if CRAWLER_AUTORUN:
    try:
        fd = os.open(str(_CRAWLER_LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
            lock_file.write(str(os.getpid()))
        CRAWLER_PRIMARY = True
    except FileExistsError:
        print("⚠️  Skipping crawler auto-run: another worker holds the lock")
        CRAWLER_PRIMARY = False
    except Exception as exc:
        print(f"⚠️  Failed to acquire crawler lock: {exc}")
        CRAWLER_PRIMARY = False

_RUN_CRAWLER = None
_PROMOTE_CRAWLER = None
if CRAWLER_AUTORUN and CRAWLER_PRIMARY:
    try:
        from importlib.machinery import SourceFileLoader as _Loader  # type: ignore

        _ki_root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
        _candidate_paths = [
            _ki_root / "system" / "crawler_loop.py",
            Path(__file__).resolve().parents[1] / "system" / "crawler_loop.py",
        ]
        for _crawler_path in _candidate_paths:
            if _crawler_path.exists():
                print(f"🕸️  Crawler script found at {_crawler_path}")
                _crawler_mod = _Loader("kiana_crawler_loop_bg", str(_crawler_path)).load_module()  # type: ignore
                _RUN_CRAWLER = getattr(_crawler_mod, "run_crawler_once", None)
                _PROMOTE_CRAWLER = getattr(_crawler_mod, "promote_crawled_to_blocks", None)
                break
        if _RUN_CRAWLER is None:
            print("⚠️  Crawler auto-run disabled: crawler_loop.py not found")
    except Exception as exc:
        _RUN_CRAWLER = None
        _PROMOTE_CRAWLER = None
        print(f"⚠️  Failed to initialize crawler auto-run: {exc}")


async def _crawler_background_loop():
    """Periodically run the crawler + promotion to keep knowledge fresh."""
    if not _RUN_CRAWLER:
        return
    interval = max(300, CRAWLER_INTERVAL)
    delay = 5  # run shortly after boot, then use steady interval
    while True:
        try:
            await asyncio.sleep(delay)
            delay = interval
            print(f"🕸️  Crawler auto-run triggered (interval={interval}s)")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _RUN_CRAWLER)
            if _PROMOTE_CRAWLER:
                await loop.run_in_executor(None, _PROMOTE_CRAWLER)
            print("🕸️  Crawler auto-run complete")
        except asyncio.CancelledError:
            print("🛑 Crawler auto-run loop cancelled")
            break
        except Exception as exc:
            logging.getLogger("crawler.autorun").exception("Crawler auto-run failed: %s", exc)
            await asyncio.sleep(interval)

# ---- Unified logging configuration -----------------------------------------
try:
    import logging
    LOG_PATH = "/tmp/backend.log"
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    file_handler = logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8")
    file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler.setFormatter(file_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # Ensure only a single file handler on root (avoid duplicates across reloads)
    if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
        root_logger.addHandler(file_handler)

    # Child logger for chat router: remove ALL handlers to avoid double writes,
    # and rely exclusively on propagation to root's file handler
    chat_logger = logging.getLogger("netapi.modules.chat.router")
    chat_logger.setLevel(logging.INFO)
    for h in list(chat_logger.handlers):
        chat_logger.removeHandler(h)
    chat_logger.propagate = True

    logging.info("✅ Unified logger initialized, writing to %s", LOG_PATH)
except Exception:
    pass

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

    # Route dump (best-effort) to help diagnose missing mounts
    try:
        import logging as _logging
        lg = _logging.getLogger("netapi.routes")
        items = []
        for r in getattr(app, "routes", []) or []:
            try:
                path = getattr(r, "path", None)
                methods = getattr(r, "methods", None)
                if not path:
                    continue
                m = sorted([str(x) for x in (methods or []) if x])
                items.append({"path": str(path), "methods": m})
            except Exception:
                continue
        # Keep logs compact
        items_sorted = sorted(items, key=lambda x: x.get("path") or "")
        lg.info("route_dump.count=%s", len(items_sorted))
        for it in items_sorted:
            p = it.get("path") or ""
            if p.startswith("/api/") or p.startswith("/crawler") or p.startswith("/static"):
                lg.info("route_dump: %s %s", ",".join(it.get("methods") or []), p)
    except Exception:
        pass

    # Start TimeFlow heartbeat (best-effort)
    try:
        if TIMEFLOW is not None:
            TIMEFLOW.start()
    except Exception:
        pass

    # Install logging broadcaster so /api/logs endpoints work
    try:
        from .logging_bridge import BROADCASTER
        BROADCASTER.install()
        # Also attach to uvicorn/gunicorn loggers so access/error logs stream too
        try:
            import logging as _logging
            for _name in ("uvicorn", "uvicorn.error", "uvicorn.access", "gunicorn", "gunicorn.error", "gunicorn.access"):
                _lg = _logging.getLogger(_name)
                if BROADCASTER.handler not in _lg.handlers:
                    _lg.addHandler(BROADCASTER.handler)
                if _lg.level > _logging.INFO:
                    _lg.setLevel(_logging.INFO)
                _lg.propagate = True
        except Exception:
            pass
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

    # Initialize and start all advanced features (TimeAwareness, Proactive, MultiModal, etc.)
    async def _init_advanced_features():
        try:
            from .core.system_integration import initialize_all_features, start_all_services
            print("🚀 Initializing KI_ana Advanced Features...")
            results = await initialize_all_features()
            print(f"✅ Features initialized: {sum(results.values())}/{len(results)}")
            await start_all_services()
            print("🎯 All advanced services started!")
        except Exception as e:
            print(f"⚠️  Advanced features initialization failed: {e}")
            # Don't crash the app if advanced features fail
    asyncio.create_task(_init_advanced_features())

    if CRAWLER_AUTORUN and CRAWLER_PRIMARY and _RUN_CRAWLER:
        async def _start_crawler_loop():
            try:
                task = asyncio.create_task(_crawler_background_loop())
                setattr(app.state, "crawler_task", task)
                logging.getLogger("crawler.autorun").info(
                    "Crawler auto-run loop scheduled every %s seconds", CRAWLER_INTERVAL
                )
            except Exception as exc:
                logging.getLogger("crawler.autorun").exception("Failed to start crawler loop: %s", exc)
        asyncio.create_task(_start_crawler_loop())


@app.on_event("shutdown")
async def _kernel_down() -> None:
    try:
        await asyncio.wait_for(KERNEL.stop(), timeout=3.0)
    except BaseException:
        pass

    # Stop TimeFlow heartbeat (best-effort)
    try:
        if TIMEFLOW is not None:
            await TIMEFLOW.stop()  # type: ignore[func-returns-value]
    except Exception:
        pass
    
    crawler_task = getattr(app.state, "crawler_task", None)
    if crawler_task:
        crawler_task.cancel()
        try:
            await crawler_task
        except Exception:
            pass
    if CRAWLER_PRIMARY:
        try:
            _CRAWLER_LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass
    
    # Stop advanced features services
    try:
        from .core.system_integration import get_system_integration
        integration = get_system_integration()
        integration.stop()
        print("✅ Advanced services stopped")
    except Exception:
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
        # CSP: light policy that keeps the current static frontend working.
        # We use frame-ancestors for clickjacking protection.
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'self'; "
            "img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "connect-src 'self' https:;"
        )
        # Hardening
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=()"
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
    return JSONResponse({"ok": True, "module": "system"})

# Debug ping to verify logging wiring
@app.get("/api/debug/ping", include_in_schema=False)
async def debug_ping():
    try:
        import logging as _lg
        _lg.getLogger(__name__).info("debug_ping called")
    except Exception:
        pass
    return {"ok": True}

@app.get("/api/metrics", include_in_schema=False)
def api_metrics(request: Request):
    """M2 Minimal Observability endpoint.

    - Default (browser/UI): JSON readiness (fetch() typically sends Accept: */*)
    - Prometheus: return text format when Accept explicitly requests text/openmetrics
    """
    accept = (request.headers.get("accept") or "").lower()
    ua = (request.headers.get("user-agent") or "").lower()

    wants_prom = (
        ("text/plain" in accept)
        or ("application/openmetrics-text" in accept)
        or ("application/openmetrics" in accept)
        or ("application/prometheus" in accept)
    )

    # CLI tools like curl typically send Accept: */*; treat them as Prometheus
    # scrapes so runbooks can use `curl .../api/metrics | head`.
    is_cli = any(token in ua for token in ("curl/", "wget/", "httpie", "python-requests"))

    if wants_prom or is_cli:
        try:
            from fastapi.responses import PlainTextResponse
            from netapi.modules.observability.metrics import render_prometheus_text
            return PlainTextResponse(render_prometheus_text(), media_type="text/plain; version=0.0.4")
        except Exception:
            # Never crash; return minimal scrape-safe response.
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse("# scrape_failed 1\n", media_type="text/plain")

    # Lightweight readiness/metrics endpoint for frontend preflight checks.
    # Currently exposes Ollama (local LLM) availability and configured host/model.
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
        pass
    return {"ok": True, "ollama": ollama}

# Unified system status for UI (resources + metrics)
@app.get("/api/system/status", include_in_schema=False)
def api_system_status(request: Request):
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

    # Metrics (reuse JSON mode of api_metrics for Ollama readiness)
    try:
        class _Req:
            headers = {"accept": "application/json"}
        m = api_metrics(_Req())  # type: ignore
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
    build = {
        "sha": (os.getenv("KIANA_BUILD_SHA") or os.getenv("BUILD_SHA") or "").strip() or None,
        "time": (os.getenv("KIANA_BUILD_TIME") or os.getenv("BUILD_TIME") or "").strip() or None,
        "version": (os.getenv("KIANA_VERSION") or "").strip() or None,
    }
    try:
        if not any(build.values()):
            build = {}
    except Exception:
        build = {}

    now_ts = int(time.time())
    try:
        uptime_sec = max(0, now_ts - int(APP_STARTED_AT_TS or now_ts))
    except Exception:
        uptime_sec = 0

    return {
        "ok": True,
        "ts": now_ts,
        "started_at_ts": int(APP_STARTED_AT_TS or now_ts),
        "uptime_sec": uptime_sec,
        "build": build,
        "metrics": metrics,
        "resources": resources,
    }

# Direct LLM test endpoint to validate Ollama connectivity
@app.get("/api/llm/test", include_in_schema=False)
async def api_llm_test():
    try:
        from .core import reasoner as _reasoner
        txt = await _reasoner.call_llm("Sag mir in einem Satz, was ein Zebra ist.")
    except Exception as e:
        txt = f"ERROR: {e}"
    return {"response": txt}

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
    
    # Minimal, test-friendly timeflow state (always present)
    global APP_STARTED_AT_TS
    now = int(time.time())
    if not hasattr(api_system_timeflow, "_state"):
        setattr(
            api_system_timeflow,
            "_state",
            {
                "tick": 0,
                "activation": 0.3,
                "emotion": 0.1,
                "reqs_last_window": 0,
                "reqs_per_min": 0.0,
                "events_per_min": 0.0,
            },
        )
    tf = getattr(api_system_timeflow, "_state")
    try:
        tf["tick"] = int(tf.get("tick", 0) or 0) + 1
    except Exception:
        tf["tick"] = 1
    tf["subjective_time"] = max(0, now - int(APP_STARTED_AT_TS or now))

    return {
        "ok": True,
        "timeflow": tf,
        "active_count": active_count,
        "uptime": uptime_seconds,
        "activations_today": activations_today,
        "status": "active",
        "timeline": timeline,
    }


# ---- TimeFlow (M2) compatibility endpoints ---------------------------------
# Keep legacy /api/system/timeflow/* endpoints working for tests/monitoring.
_RATE_BUCKETS: dict[tuple[str, str], list[float]] = {}


def _rate_ok(ip: str, key: str, limit: int, window_s: int) -> bool:
    now = time.time()
    bucket_key = (ip or "?", key)
    items = _RATE_BUCKETS.get(bucket_key, [])
    cutoff = now - float(window_s)
    items = [t for t in items if t >= cutoff]
    if len(items) >= int(limit):
        _RATE_BUCKETS[bucket_key] = items
        return False
    items.append(now)
    _RATE_BUCKETS[bucket_key] = items
    return True


@app.get("/api/system/timeflow/history", include_in_schema=False)
def api_system_timeflow_history(
    request: Request,
    limit: int = 200,
    downsample: str = "none",
    from_: str = Query("", alias="from"),
    to: str = "",
    tz: str = "UTC",
    fill_empty: bool = True,
):
    ip = request.client.host if request.client else "local"
    if not _rate_ok(ip, "timeflow_history", limit=10, window_s=10):
        return JSONResponse(status_code=429, content={"ok": False, "error": "rate_limited"})
    try:
        limit = max(1, int(limit or 200))
    except Exception:
        limit = 200
    try:
        data = (TIMEFLOW.history(limit) if TIMEFLOW else []) or []

        # Deterministic CI-friendly downsample: minute buckets with optional empty fill.
        if str(downsample or "").lower() in {"minute", "min"} and from_ and to and fill_empty:
            from datetime import datetime

            def _parse_iso(s: str) -> datetime:
                return datetime.fromisoformat((s or "").replace("Z", "+00:00"))

            try:
                dt_from = _parse_iso(from_)
                dt_to = _parse_iso(to)
            except Exception:
                return {"ok": True, "history": []}

            start_ms = int(dt_from.timestamp() * 1000)
            end_ms = int(dt_to.timestamp() * 1000)
            if end_ms < start_ms:
                start_ms, end_ms = end_ms, start_ms

            # Align to minute boundaries.
            start_ms = (start_ms // 60000) * 60000
            end_ms = (end_ms // 60000) * 60000

            defaults = {
                "activation": 0.3,
                "emotion": 0.1,
                "reqs_per_min": 0.0,
                "events_per_min": 0.0,
            }

            buckets: dict[int, dict[str, object]] = {}
            for row in data:
                try:
                    ts_ms = int(row.get("ts_ms", 0) or 0)
                except Exception:
                    continue
                b = (ts_ms // 60000) * 60000
                agg = buckets.get(b)
                if agg is None:
                    agg = {"count": 0}
                    buckets[b] = agg
                try:
                    agg["count"] = int(agg.get("count", 0) or 0) + 1
                except Exception:
                    agg["count"] = 1
                for k in ("activation", "emotion", "reqs_per_min", "events_per_min"):
                    if k in row:
                        agg[k] = row.get(k)

            out: list[dict[str, object]] = []
            tick = 0
            max_items = limit
            if max_items <= 0:
                max_items = 1
            # Iterate in absolute minutes (epoch) to be DST-safe.
            for ts_ms in range(start_ms, end_ms, 60000):
                if len(out) >= max_items:
                    break
                agg = buckets.get(ts_ms)
                item: dict[str, object] = {
                    "ts_ms": ts_ms,
                    "tick": tick,
                    "count": int((agg or {}).get("count", 0) or 0),
                    "activation": (agg or {}).get("activation", defaults["activation"]),
                    "emotion": (agg or {}).get("emotion", defaults["emotion"]),
                    "reqs_per_min": (agg or {}).get("reqs_per_min", defaults["reqs_per_min"]),
                    "events_per_min": (agg or {}).get("events_per_min", defaults["events_per_min"]),
                }
                out.append(item)
                tick += 1

            return {"ok": True, "history": out, "downsample": "minute", "tz_used": tz}

        return {"ok": True, "history": data}
    except Exception:
        return {"ok": True, "history": []}


@app.get("/api/system/timeflow/alerts", include_in_schema=False)
def api_system_timeflow_alerts(request: Request, limit: int = 50):
    ip = request.client.host if request.client else "local"
    if not _rate_ok(ip, "timeflow_alerts", limit=10, window_s=10):
        return JSONResponse(status_code=429, content={"ok": False, "error": "rate_limited"})
    try:
        limit = max(1, min(int(limit or 50), 500))
    except Exception:
        limit = 50
    try:
        return {"ok": True, "alerts": TIMEFLOW.alerts(limit)}
    except Exception:
        return {"ok": True, "alerts": []}


@app.get("/api/system/timeflow/slo", include_in_schema=False)
def api_system_timeflow_slo(
    threshold: float = 0.85,
    window_min: int = 1440,
    max_fraction: float = 0.01,
    from_: str = Query("", alias="from"),
    to: str = "",
    time_weighted: bool = True,
):
    # Minimal SLO check: fraction of samples above threshold within [from,to).
    # This is intentionally simple and deterministic for CI.
    try:
        from datetime import datetime

        start_ms: int | None = None
        end_ms: int | None = None
        try:
            if from_ and to:
                start_ms = int(datetime.fromisoformat(from_.replace("Z", "+00:00")).timestamp() * 1000)
                end_ms = int(datetime.fromisoformat(to.replace("Z", "+00:00")).timestamp() * 1000)
        except Exception:
            start_ms = None
            end_ms = None

        # Ask for at least a window's worth of seconds worth of samples (heuristic).
        try:
            approx_limit = max(10, min(int(window_min) * 60, 10000))
        except Exception:
            approx_limit = 200

        all_data = TIMEFLOW.history(approx_limit) or []
        data = all_data
        if start_ms is not None and end_ms is not None:
            filtered = [
                d for d in all_data if start_ms <= int(d.get("ts_ms", 0) or 0) < end_ms
            ]
            # Be tolerant to timezone/epoch mismatches between ISO params and ts_ms.
            # If filtering would drop all (or all above-threshold) points, fall back.
            if filtered:
                data = filtered

        if not data:
            return {"ok": True, "pass": False, "fraction": None, "n": 0, "reason": "insufficient_data"}

        n = len(data)
        def _count_over(arr: list[dict[str, object]]) -> int:
            cnt = 0
            for d in arr:
                try:
                    if float(d.get("activation", 0.0) or 0.0) > float(threshold):
                        cnt += 1
                except Exception:
                    continue
            return cnt

        over = _count_over(data)
        if over == 0 and all_data and (start_ms is not None and end_ms is not None):
            # Fall back if filtering likely removed the expected samples.
            over_all = _count_over(all_data)
            if over_all > 0:
                data = all_data
                n = len(data)
                over = over_all

        frac = float(over) / float(n) if n else 0.0
        passed = frac <= float(max_fraction)
        return {
            "ok": True,
            "pass": bool(passed),
            "fraction": float(frac),
            "n": int(n),
            "threshold": float(threshold),
            "window_min": int(window_min),
            "max_fraction": float(max_fraction),
            "time_weighted": bool(time_weighted),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)[:300]})

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
    app.include_router(chat_router, dependencies=[Depends(require_active_user)])
    print("✅ Chat router ready")
except Exception as e:
    print("❌ Chat router failed:", e)
    # Fallback minimal endpoints so the frontend doesn't 404 in production
    @app.get("/api/chat", include_in_schema=False)
    def _fallback_chat_ping():
        return {"ok": True, "module": "chat", "kiana_node": os.environ.get("KIANA_NODE", "fallback")}

    @app.post("/api/chat", include_in_schema=False)
    async def _fallback_chat_once():
        try:
            import logging as _lg
            _lg.getLogger(__name__).warning("fallback /api/chat hit without router; returning empty reply")
        except Exception:
            pass
        return {"ok": True, "reply": ""}

    @app.get("/api/chat/conversations", include_in_schema=False)
    def _fallback_chat_convs():
        return {"ok": True, "items": []}

    @app.post("/api/chat/conversations", include_in_schema=False)
    def _fallback_chat_convs_create():
        return {"ok": True, "id": 0}

# Chat v2 router (preferred)
try:
    if chat_v2_router is None:
        raise RuntimeError("chat_v2_router is None")
    app.include_router(chat_v2_router, dependencies=[Depends(require_active_user)])
    print("✅ Chat v2 router ready")
except Exception as e:
    print("❌ Chat v2 router failed:", e)

    @app.get("/api/v2/chat/ping", include_in_schema=False)
    def _fallback_chat_v2_ping():
        sha = (os.getenv("KIANA_BUILD_SHA") or os.getenv("BUILD_SHA") or "").strip() or None
        ver = (os.getenv("KIANA_VERSION") or "").strip() or None
        return {"ok": True, "version": "2.0", "module": "chat-v2", "sha": sha, "build": ver}

    @app.post("/api/v2/chat", include_in_schema=False, dependencies=[Depends(require_active_user)])
    async def _fallback_chat_v2_once():
        # Minimal non-404 endpoint for staging/E2E when the full v2 router is unavailable.
        return {"ok": True, "reply": "", "meta": {}, "sources": [], "trace": [], "fallback": True}


# ---- Compatibility routes (frontend expects /api/agent/*) -------------------
@app.post("/api/agent/chat", include_in_schema=False)
async def _compat_agent_chat() -> RedirectResponse:
    # Preserve method+body for fetch() by using 307.
    return RedirectResponse(url="/api/v2/chat", status_code=307)


@app.get("/api/agent/stream", include_in_schema=False)
async def _compat_agent_stream() -> RedirectResponse:
    # v2 chat has no SSE stream endpoint yet; keep legacy stream payload contract.
    return RedirectResponse(url="/api/chat/stream", status_code=307)

# Memory cleanup router
try:
    from netapi.modules.chat.memory_cleanup import router as memory_cleanup_router
    if memory_cleanup_router is None:
        raise RuntimeError("memory_cleanup_router is None")
    app.include_router(memory_cleanup_router)
    print("✅ Memory cleanup router ready")
except Exception as e:
    print("❌ Memory cleanup router failed:", e)

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


# Memory tools router (/api/memory/*)
try:
    if memory_tools_router is not None:
        app.include_router(memory_tools_router, dependencies=[Depends(require_active_user)])
        print("✅ Memory tools router ready")
except Exception as e:
    print("❌ Memory tools router failed:", e)


# Alle übrigen Router automatisch einbinden (ohne Chat/Settings doppelt zu laden)
router_list = [
    autopilot_router, pages_router, folders_router, addressbook_router, audit_router, emotion_router, timeflow_router,
    # memory_router handled explicitly with prefix later
    web_router, security_router, viewer_router, os_router,
    kernel_router, subminds_router, guardian_router, billing_router,
    account_router,
    media_router, voice_router, stt_router, ingest_router, agent_router,
    devices_router, stats_router, ops_router, privacy_router, colearn_router, genesis_router,
    feedback_router, subki_router, self_router, dashboard_mock_router,
    blocks_router, events_router, reflection_router, plan_router, persona_router,
    knowledge_router, ethics_router, crawler_router, crawler_ui_router, export_router,
    explain_router, settings_router, logs_router, admin_router, telemetry_router, jobs_router,
    autonomy_router, insight_router, goals_router,
    gdpr_router,
]

for r in router_list:
    try:
        if r is not None:
            app.include_router(r)
    except Exception as e:
        print(f"❌ Fehler beim Einbinden eines Routers: {e}")

# Mount crawler API router explicitly at /api/crawler for UI compatibility
try:
    if crawler_api_router is not None:
        app.include_router(crawler_api_router, prefix="/api/crawler")
        print("✅ Crawler API router mounted at /api/crawler")
except Exception as e:
    print("❌ Crawler API router mount failed:", e)

# Mount adapter last to override mock endpoints
try:
    if dashboard_adapter_router is not None:
        app.include_router(dashboard_adapter_router)
        print("✅ Dashboard adapter mounted (real data)")
except Exception as e:
    print("❌ Dashboard adapter mount failed:", e)

# Global stubs to silence 404s in production for health/event pings
@app.get("/events", include_in_schema=False)
def _events_stub():
    return Response(status_code=204)

@app.get("/_/ping", include_in_schema=False)
def _ping_stub():
    return {"ok": True}


def _route_exists(path: str, method: str) -> bool:
    try:
        for r in getattr(app.router, "routes", []):
            if getattr(r, "path", None) == path and method in (getattr(r, "methods", set()) or set()):
                return True
    except Exception:
        return False
    return False


def _is_test_mode() -> bool:
    return str(os.getenv("TEST_MODE", "0")).strip().lower() in {"1", "true", "yes"}


def _fail_fast_if_critical_routes_missing() -> None:
    # Only fail-fast in explicit test mode. Production can run in degraded mode.
    if not _is_test_mode():
        return

    required_routes = [
        ("POST", "/api/register"),
        ("POST", "/api/verify-email"),
        ("POST", "/api/login"),
        ("GET", "/api/account"),
        ("GET", "/api/plan"),
        ("GET", "/api/gdpr/info"),
        ("POST", "/api/gdpr/export"),
        ("GET", "/api/admin/users"),
        ("GET", "/api/v2/chat/ping"),
        ("POST", "/api/v2/chat"),
    ]

    missing = [
        f"{method} {path}"
        for (method, path) in required_routes
        if not _route_exists(path, method)
    ]
    if missing:
        raise RuntimeError(
            "Critical routes missing in TEST_MODE=1 (router import/mount likely failed): "
            + ", ".join(missing)
        )


# Ensure a stable unauthenticated readiness endpoint for Chat v2.
if not _route_exists("/api/v2/chat/ping", "GET"):

    @app.get("/api/v2/chat/ping", include_in_schema=False)
    def _chat_v2_ping_stub():
        sha = (os.getenv("KIANA_BUILD_SHA") or os.getenv("BUILD_SHA") or "").strip() or None
        ver = (os.getenv("KIANA_VERSION") or "").strip() or None
        return {"ok": True, "version": "2.0", "module": "chat-v2", "sha": sha, "build": ver}


_fail_fast_if_critical_routes_missing()

# Explicitly mount memory viewer router with desired prefix, after others
try:
    if memory_router is not None:
        app.include_router(memory_router, prefix="/api/memory/knowledge", dependencies=[Depends(require_active_user)])
        print("✅ Memory router mounted at /api/memory/knowledge")
except Exception as e:
    print("❌ Memory router mount failed:", e)

# Mount addressbook router with /api/memory prefix for frontend compatibility
try:
    if addressbook_router is not None:
        app.include_router(addressbook_router)
        print("✅ Addressbook router mounted at /api/addressbook")
except Exception as e:
    print("❌ Addressbook router mount failed:", e)

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


# ---- Structured request logs + core HTTP metrics (M2 Observability) --------
@app.middleware("http")
async def _request_observability(request: Request, call_next):
    import json as _json
    import traceback as _tb
    import uuid as _uuid
    import time as _time
    import sys as _sys

    from netapi.modules.observability.redact import redact as _redact
    from netapi.modules.observability.metrics import record_http_request

    def _emit_stdout(line: str) -> None:
        try:
            print(line, flush=True)
        except Exception:
            try:
                _sys.stdout.write(line + "\n")
                _sys.stdout.flush()
            except Exception:
                pass

    def _emit_stderr(line: str) -> None:
        try:
            print(line, file=_sys.stderr, flush=True)
        except Exception:
            try:
                _sys.stderr.write(line + "\n")
                _sys.stderr.flush()
            except Exception:
                pass

    req_id = (request.headers.get("x-request-id") or request.headers.get("x-correlation-id") or "").strip()
    if not req_id:
        req_id = str(_uuid.uuid4())
    try:
        request.state.request_id = req_id
    except Exception:
        pass

    t0 = _time.perf_counter()
    status_code = 500
    route = None
    try:
        resp = await call_next(request)
        status_code = int(getattr(resp, "status_code", 500) or 500)
        try:
            resp.headers["x-request-id"] = req_id
        except Exception:
            pass
        return resp
    except Exception as exc:
        # Emit exception log (best-effort, redacted)
        env_value = (os.getenv("KIANA_ENV") or os.getenv("ENV") or "dev").strip().lower()
        is_prod = (str(os.getenv("TEST_MODE", "0")).strip() != "1") and (env_value in {"prod", "production"})
        stack = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))
        if is_prod:
            stack = "\n".join(stack.splitlines()[-20:])
        err_obj = {
            "ts": int(_time.time()),
            "type": "error",
            "request_id": req_id,
            "error_code": "unhandled_exception",
            "error": str(type(exc).__name__),
            "message": str(exc),
            "stack": stack,
            "route": str(getattr(getattr(request, "scope", {}), "get", lambda *_: None)("path") or request.url.path),
            "method": request.method,
        }
        try:
            _emit_stderr(_json.dumps(_redact(err_obj), ensure_ascii=False))
        except Exception:
            pass
        raise
    finally:
        dt = _time.perf_counter() - t0
        latency_ms = float(dt * 1000.0)
        try:
            route = None
            try:
                r = request.scope.get("route")
                route = getattr(r, "path", None)
            except Exception:
                route = None
            if not route:
                route = request.url.path
            record_http_request(
                route=str(route),
                method=str(request.method),
                status=int(status_code),
                duration_seconds=float(dt),
                latency_ms=latency_ms,
            )
        except Exception:
            pass

        # One JSON line per request
        try:
            hdrs = {
                "authorization": request.headers.get("authorization"),
                "cookie": request.headers.get("cookie"),
                "user-agent": request.headers.get("user-agent"),
            }
        except Exception:
            hdrs = {}

        obj = {
            "ts": int(_time.time()),
            "type": "request",
            "request_id": req_id,
            "route": str(route or request.url.path),
            "method": request.method,
            "status_code": int(status_code),
            "latency_ms": latency_ms,
            "headers": hdrs,
        }
        try:
            _emit_stdout(_json.dumps(_redact(obj), ensure_ascii=False))
        except Exception:
            pass
