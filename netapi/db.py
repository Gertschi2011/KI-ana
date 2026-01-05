# netapi/db.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# -----------------------------
# Config: DATABASE_URL via env/.env
# -----------------------------

def _load_env_from_file() -> None:
    """Load .env if present under KI_ROOT (or project root). Does nothing if env already set."""
    if os.getenv("DATABASE_URL"):
        return
    try:
        ki_root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))).resolve()
    except Exception:
        ki_root = Path.home() / "ki_ana"
    for p in (ki_root / ".env", ki_root.parent / ".env"):
        try:
            if p.exists():
                for line in p.read_text(encoding="utf-8").splitlines():
                    if not line or line.strip().startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip(); v = v.strip().strip('"').strip("'")
                    if k and v and k not in os.environ:
                        os.environ[k] = v
                break
        except Exception:
            pass

_load_env_from_file()

def _default_sqlite_url() -> str:
    try:
        root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))).resolve()
    except Exception:
        root = Path.home() / "ki_ana"
    db_path = root / "netapi" / "users.db"
    return f"sqlite:///{db_path}"

def _current_db_url() -> str:
    # Re-load .env only if DATABASE_URL is not explicitly set.
    _load_env_from_file()
    return os.getenv("DATABASE_URL", _default_sqlite_url()).strip()


DB_URL = _current_db_url()


def _make_engine(db_url: str):
    is_sqlite_local = db_url.startswith("sqlite:")
    return create_engine(
        db_url,
        connect_args=({"check_same_thread": False} if is_sqlite_local else {}),
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        pool_pre_ping=True,
        future=True,
    )


# -----------------------------
# Engine creation (supports runtime reconfiguration)
# -----------------------------
is_sqlite = DB_URL.startswith("sqlite:")
engine = _make_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_engine_current() -> None:
    """Ensure engine/sessionmaker reflect the current DATABASE_URL.

    This is mainly to support tests that set DATABASE_URL per-test, even if
    netapi.db was imported earlier.
    """

    global DB_URL, engine, SessionLocal, is_sqlite

    env_url = _current_db_url()
    if not env_url or env_url == DB_URL:
        return

    try:
        engine.dispose()
    except Exception:
        pass

    DB_URL = env_url
    is_sqlite = DB_URL.startswith("sqlite:")
    engine = _make_engine(DB_URL)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db() -> Generator:
    """FastAPI dependency-style session generator (optional)."""
    ensure_engine_current()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Create tables if they don't exist.
    This only creates; it won't drop anything.
    """
    ensure_engine_current()
    # Import models inside function to avoid circular import at module load time.
    from . import models  # noqa: F401  (registers core models to Base metadata)
    # Ensure folders model is also registered (Conversation.folder_id -> folders.id)
    try:
        import netapi.modules.chat.folders  # noqa: F401
    except Exception:
        pass
    Base.metadata.create_all(bind=engine)


def ensure_columns() -> None:
    """
    Lightweight, safe migration helper for SQLite:
    Adds missing columns on 'users' table if absent.
    No data loss, no rename, only simple 'ADD COLUMN'.
    """
    ensure_engine_current()
    wanted = {
        "plan": "TEXT DEFAULT 'free'",
        "plan_until": "INTEGER DEFAULT 0",
        "birthdate": "TEXT",
        "address": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
        # New role/tier/quota fields (idempotent ADD COLUMNs)
        "role": "TEXT DEFAULT 'user'",
        "tier": "TEXT DEFAULT 'user'",
        "daily_quota": "INTEGER DEFAULT 20",
        "quota_reset_at": "INTEGER DEFAULT 0",
        # M2: SaaS Auth gates
        "email_verified": "INTEGER DEFAULT 0",
        "account_status": "TEXT DEFAULT 'pending_verification'",
        "subscription_status": "TEXT DEFAULT 'inactive'",
        # M2-BLOCK2: grace period for canceled subscriptions
        "subscription_grace_until": "INTEGER DEFAULT 0",
        # M2: brute-force mitigation helpers (optional)
        "failed_login_count": "INTEGER DEFAULT 0",
        "locked_until": "INTEGER DEFAULT 0",

        # M2-BLOCK5: GDPR consent + deletion lifecycle
        "consent_learning": "TEXT DEFAULT 'ask'",
        "delete_requested_at": "INTEGER DEFAULT 0",
        "delete_scheduled_for": "INTEGER DEFAULT 0",
        "deleted_at": "INTEGER DEFAULT 0",
    }
    # Use SQLAlchemy inspector for database-agnostic table/column checks
    from sqlalchemy import inspect
    inspector = inspect(engine)
    
    # Check if users table exists
    if 'users' not in inspector.get_table_names():
        return
    
    with engine.begin() as conn:
        # Get existing columns
        columns = inspector.get_columns('users')
        have = {c['name'] for c in columns}
        
        for col, ddl in wanted.items():
            if col not in have:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {ddl}"))

    # Ensure api_usage table exists (for per-day counters)
    if 'api_usage' not in inspector.get_table_names():
        try:
            with engine.begin() as conn:
                # Use SERIAL for PostgreSQL compatibility (AUTO_INCREMENT equivalent)
                conn.execute(text(
                    """
                    CREATE TABLE IF NOT EXISTS api_usage (
                      id SERIAL PRIMARY KEY,
                      user_id INTEGER NOT NULL,
                      date TEXT NOT NULL,
                      feature TEXT NOT NULL DEFAULT 'chat',
                      count INTEGER NOT NULL DEFAULT 0
                    );
                    """
                ))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_api_usage_user_date_feature ON api_usage(user_id, date, feature)"))
        except Exception as e:
            # Table might already exist from a parallel worker, that's OK
            pass
    else:
        # If api_usage exists, ensure it has the 'feature' column and correct unique index.
        try:
            cols = inspector.get_columns('api_usage')
            have_cols = {c['name'] for c in (cols or [])}
            with engine.begin() as conn:
                if 'feature' not in have_cols:
                    conn.execute(text("ALTER TABLE api_usage ADD COLUMN feature TEXT NOT NULL DEFAULT 'chat'"))
                # Best-effort: create the new unique index (old one may still exist).
                try:
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_api_usage_user_date_feature ON api_usage(user_id, date, feature)"))
                except Exception:
                    pass
        except Exception:
            pass

    # Ensure api_usage_minute table exists (for per-minute counters)
    if 'api_usage_minute' not in inspector.get_table_names():
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    """
                    CREATE TABLE IF NOT EXISTS api_usage_minute (
                      id SERIAL PRIMARY KEY,
                      user_id INTEGER NOT NULL,
                      bucket TEXT NOT NULL,
                      feature TEXT NOT NULL,
                      count INTEGER NOT NULL DEFAULT 0
                    );
                    """
                ))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_api_usage_minute_user_bucket_feature ON api_usage_minute(user_id, bucket, feature)"))
        except Exception:
            pass


def ensure_knowledge_indexes() -> None:
    """
    Ensure helpful indexes exist on knowledge_blocks (SQLite):
    - UNIQUE index on hash
    - index on ts (descending queries), source (LIKE), tags (LIKE)
    All ops are idempotent and safe if the table or columns are absent.
    """
    try:
        ensure_engine_current()
        if not DB_URL.startswith("sqlite:"):
            return
        
        from sqlalchemy import inspect
        inspector = inspect(engine)
        
        # Check table exists
        if 'knowledge_blocks' not in inspector.get_table_names():
            return
        
        with engine.begin() as conn:
            # Discover existing indexes
            idx_rows = conn.execute(text("PRAGMA index_list('knowledge_blocks')")).fetchall()
            have_idx = {str(r[1]) for r in idx_rows} if idx_rows else set()
            # UNIQUE on hash
            if "idx_kb_hash_unique" not in have_idx:
                try:
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_kb_hash_unique ON knowledge_blocks(hash)"))
                except Exception:
                    pass
            # INDEX on ts
            if "idx_kb_ts" not in have_idx:
                try:
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kb_ts ON knowledge_blocks(ts DESC, id DESC)"))
                except Exception:
                    pass
            # INDEX on source
            if "idx_kb_source" not in have_idx:
                try:
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kb_source ON knowledge_blocks(source)"))
                except Exception:
                    pass
            # INDEX on tags
            if "idx_kb_tags" not in have_idx:
                try:
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kb_tags ON knowledge_blocks(tags)"))
                except Exception:
                    pass

            # Create FTS5 virtual table (contentless mode referencing knowledge_blocks)
            try:
                conn.execute(text(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_blocks_fts
                    USING fts5(source, tags, content, content='knowledge_blocks', content_rowid='id');
                    """
                ))
            except Exception:
                # ignore if FTS5 not available
                pass

            # Create triggers to keep FTS in sync
            try:
                conn.execute(text(
                    """
                    CREATE TRIGGER IF NOT EXISTS kb_ai AFTER INSERT ON knowledge_blocks
                    BEGIN
                      INSERT INTO knowledge_blocks_fts(rowid, source, tags, content)
                      VALUES (new.id, new.source, new.tags, new.content);
                    END;
                    """
                ))
            except Exception:
                pass
            try:
                conn.execute(text(
                    """
                    CREATE TRIGGER IF NOT EXISTS kb_au AFTER UPDATE ON knowledge_blocks
                    BEGIN
                      INSERT INTO knowledge_blocks_fts(knowledge_blocks_fts, rowid, source, tags, content)
                      VALUES('delete', old.id, old.source, old.tags, old.content);
                      INSERT INTO knowledge_blocks_fts(rowid, source, tags, content)
                      VALUES (new.id, new.source, new.tags, new.content);
                    END;
                    """
                ))
            except Exception:
                pass
            try:
                conn.execute(text(
                    """
                    CREATE TRIGGER IF NOT EXISTS kb_ad AFTER DELETE ON knowledge_blocks
                    BEGIN
                      INSERT INTO knowledge_blocks_fts(knowledge_blocks_fts, rowid, source, tags, content)
                      VALUES('delete', old.id, old.source, old.tags, old.content);
                    END;
                    """
                ))
            except Exception:
                pass
    except Exception:
        # never crash app on index ensure
        pass


def query_db(sql: str, params: tuple | list = ()):
    """Execute a SQL statement against the configured engine.
    - For SELECT: returns list[dict]
    - For non-SELECT: executes and commits, returns []
    """
    sql_stripped = (sql or "").strip().lower()
    with engine.begin() as conn:
        res = conn.execute(text(sql), params if isinstance(params, (tuple, list)) else ())
        if sql_stripped.startswith("select"):
            rows = res.fetchall()
            if not rows:
                return []
            keys = res.keys()
            return [{k: row[i] for i, k in enumerate(keys)} for row in rows]
        else:
            # DDL/DML auto-committed by engine.begin()
            return []

# -----------------------------
# Audit helpers (lightweight, read-only)
# -----------------------------
def count_memory_per_day(limit: int = 7):
    """Return last N days with counts of saved knowledge blocks.
    Expects a 'ts' integer (unix seconds) column on knowledge_blocks.
    """
    try:
        dialect = ""
        try:
            dialect = str(getattr(getattr(engine, "dialect", None), "name", "") or "").lower()
        except Exception:
            dialect = ""

        if dialect.startswith("postgres"):
            sql = """
            SELECT to_char(to_timestamp(ts), 'YYYY-MM-DD') AS day, COUNT(*) AS cnt
            FROM knowledge_blocks
            GROUP BY day
            ORDER BY day DESC
            """
        else:
            # SQLite (and default fallback)
            sql = """
            SELECT strftime('%Y-%m-%d', ts, 'unixepoch') AS day, COUNT(*) AS cnt
            FROM knowledge_blocks
            GROUP BY day
            ORDER BY day DESC
            """

        rows = query_db(sql)
        return rows[: max(1, int(limit))] if rows else []
    except Exception:
        return []

def top_sources(limit: int = 5):
    """Return top sources (by count) from knowledge_blocks."""
    try:
        rows = query_db(
            """
            SELECT COALESCE(source, '') AS source, COUNT(*) AS cnt
            FROM knowledge_blocks
            GROUP BY source
            ORDER BY cnt DESC
            """
        )
        return rows[: max(1, int(limit))] if rows else []
    except Exception:
        return []

def total_blocks() -> int:
    """Return total number of knowledge_blocks."""
    try:
        rows = query_db("SELECT COUNT(*) AS c FROM knowledge_blocks")
        if rows and isinstance(rows, list) and rows[0].get("c") is not None:
            return int(rows[0]["c"])
    except Exception:
        pass
    return 0
