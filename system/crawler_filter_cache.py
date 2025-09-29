#!/usr/bin/env python3
import sqlite3, time
from pathlib import Path
from typing import Optional

BASE_DIR = Path.home() / "ki_ana"
CACHE_DIR = BASE_DIR / "system" / "cache"
DB_PATH = CACHE_DIR / "crawler_cache.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS fetches (
  url TEXT PRIMARY KEY,
  content_hash TEXT,
  last_seen_ts INTEGER
);
CREATE INDEX IF NOT EXISTS idx_fetches_hash ON fetches(content_hash);
"""

def _conn():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    return conn


def ensure_db() -> None:
    with _conn() as c:
        c.executescript(SCHEMA)
        c.commit()


def now_ts() -> int:
    return int(time.time())


def should_fetch(url: str, ttl_days: int = 7) -> bool:
    """True if URL hasn't been seen within TTL."""
    ensure_db()
    cutoff = now_ts() - ttl_days * 86400
    with _conn() as c:
        row = c.execute("SELECT last_seen_ts FROM fetches WHERE url=?", (url,)).fetchone()
        if not row:
            return True
        last_seen = int(row[0] or 0)
        return last_seen < cutoff


def content_seen(content_hash: str, ttl_days: Optional[int] = None) -> bool:
    """True if identical content hash is present (optionally constrained by TTL)."""
    ensure_db()
    with _conn() as c:
        if ttl_days is None:
            row = c.execute("SELECT 1 FROM fetches WHERE content_hash=? LIMIT 1", (content_hash,)).fetchone()
            return bool(row)
        cutoff = now_ts() - ttl_days * 86400
        row = c.execute(
            "SELECT 1 FROM fetches WHERE content_hash=? AND last_seen_ts>=? LIMIT 1",
            (content_hash, cutoff),
        ).fetchone()
        return bool(row)


def record_fetch(url: str, content_hash: str, ts: Optional[int] = None) -> None:
    ensure_db()
    ts = int(ts or now_ts())
    with _conn() as c:
        c.execute(
            "INSERT INTO fetches(url, content_hash, last_seen_ts) VALUES(?,?,?)\n"
            "ON CONFLICT(url) DO UPDATE SET content_hash=excluded.content_hash, last_seen_ts=excluded.last_seen_ts",
            (url, content_hash, ts),
        )
        c.commit()


def vacuum_if_needed(max_size_mb: int = 64) -> None:
    try:
        if DB_PATH.exists() and DB_PATH.stat().st_size > max_size_mb * 1024 * 1024:
            with _conn() as c:
                c.execute("VACUUM")
    except Exception:
        pass
