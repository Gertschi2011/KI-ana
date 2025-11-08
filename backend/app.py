from __future__ import annotations
import os
from datetime import timedelta
from flask import Flask, jsonify
from flask_cors import CORS

from backend.core.config import Settings
from backend.core.logging import configure_logging
from backend.core.db import init_db, Session, Base
from backend.core.rate_limit import limiter
from backend.core.otel import init_tracing
from backend.auth.routes import bp as auth_bp
from backend.auth.routes import (
    me as auth_me,
    login as auth_login,
    logout as auth_logout,
    register as auth_register,
)
from backend.routes.ingest import bp as ingest_bp
from backend.routes.memory import bp as memory_bp
from backend.routes.search import bp as search_bp
from backend.routes.orchestrator import bp as orchestrator_bp
from backend.routes.logs import bp as logs_bp
from backend.services.emergency import emergency_active


def create_app() -> Flask:
    settings = Settings()
    app = Flask(__name__)
    app.config.update(
        JSON_SORT_KEYS=False,
        PROPAGATE_EXCEPTIONS=True,
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    )

    CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": settings.cors_origins}})

    # logging & tracing
    configure_logging()
    init_tracing(service_name="kiana-backend")

    # DB init
    init_db()

    # Rate limiter
    limiter.init_app(app)

    # Blueprints
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(ingest_bp, url_prefix="/api/ingest")
    app.register_blueprint(memory_bp, url_prefix="/api/memory")
    app.register_blueprint(search_bp, url_prefix="/api/search")
    app.register_blueprint(orchestrator_bp, url_prefix="/api/jarvis")
    app.register_blueprint(logs_bp, url_prefix="/api/logs")

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "emergency": emergency_active()})

    # --- Compatibility aliases for legacy static pages ---
    # Map old knowledge viewer endpoints to new memory routes
    from backend.routes.memory import list_blocks, append_block  # type: ignore

    @app.get("/api/memory/knowledge/list")
    def knowledge_list_alias():
        return list_blocks()

    @app.post("/api/memory/knowledge/append")
    def knowledge_append_alias():
        return append_block()

    # --- Aliases to support /api/* directly (in addition to /api/auth/*) ---
    @app.get("/api/me")
    def api_me_alias():
        return auth_me()  # delegate to auth blueprint handler

    @app.post("/api/login")
    def api_login_alias():
        return auth_login()

    @app.post("/api/logout")
    def api_logout_alias():
        return auth_logout()

    @app.post("/api/register")
    def api_register_alias():
        return auth_register()

    @app.get("/")
    def root():
        return jsonify({"ok": True, "app": "KI_ana API"})

    return app


if __name__ == "__main__":
    # for local debug only
    app = create_app()
    app.run(host="0.0.0.0", port=8000)
