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

DB_URL = os.getenv("DATABASE_URL", _default_sqlite_url()).strip()

# -----------------------------
# Engine creation
# -----------------------------
is_sqlite = DB_URL.startswith("sqlite:")
engine = create_engine(
    DB_URL,
    connect_args=({"check_same_thread": False} if is_sqlite else {}),
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db() -> Generator:
    """FastAPI dependency-style session generator (optional)."""
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
    # Import models inside function to avoid circular import at module load time.
    from . import models  # noqa: F401  (registers models to Base metadata)
    Base.metadata.create_all(bind=engine)


def ensure_columns() -> None:
    """
    Lightweight, safe migration helper for SQLite:
    Adds missing columns on 'users' table if absent.
    No data loss, no rename, only simple 'ADD COLUMN'.
    """
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
                      count INTEGER NOT NULL DEFAULT 0
                    );
                    """
                ))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_api_usage_user_date ON api_usage(user_id, date)"))
        except Exception as e:
            # Table might already exist from a parallel worker, that's OK
            pass


def ensure_knowledge_indexes() -> None:
    """
    Ensure helpful indexes exist on knowledge_blocks (SQLite):
    - UNIQUE index on hash
    - index on ts (descending queries), source (LIKE), tags (LIKE)
    All ops are idempotent and safe if the table or columns are absent.
    """
    try:
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
        rows = query_db(
            """
            SELECT strftime('%Y-%m-%d', ts, 'unixepoch') AS day, COUNT(*) AS cnt
            FROM knowledge_blocks
            GROUP BY day
            ORDER BY day DESC
            """
        )
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
