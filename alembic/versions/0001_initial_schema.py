"""
Initial schema alignment with current models and lightweight SQLite-safe adjustments.

- Ensures users table has role, tier, daily_quota, quota_reset_at
- Ensures api_usage table + unique index exist

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2025-09-14
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Create tables from metadata if missing
    # Note: We avoid importing models here; rely on idempotent checks
    # Add missing columns to users (SQLite-safe)
    try:
        res = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'"))
        if not res.fetchone():
            # Minimal create if entirely missing (subset, rest is created by app on boot)
            conn.execute(sa.text(
                """
                CREATE TABLE users (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  email TEXT UNIQUE,
                  password_hash TEXT,
                  birthdate TEXT,
                  address TEXT,
                  role TEXT DEFAULT 'user',
                  tier TEXT DEFAULT 'user',
                  is_papa INTEGER DEFAULT 0,
                  daily_quota INTEGER DEFAULT 20,
                  quota_reset_at INTEGER DEFAULT 0,
                  plan TEXT DEFAULT 'free',
                  plan_until INTEGER DEFAULT 0,
                  created_at INTEGER,
                  updated_at INTEGER DEFAULT 0
                )
                """
            ))
        # Add columns if missing
        cols = conn.execute(sa.text("PRAGMA table_info(users)")).fetchall()
        have = {c[1] for c in cols}
        wanted = {
            'role': "TEXT DEFAULT 'user'",
            'tier': "TEXT DEFAULT 'user'",
            'daily_quota': "INTEGER DEFAULT 20",
            'quota_reset_at': "INTEGER DEFAULT 0",
            'plan': "TEXT DEFAULT 'free'",
            'plan_until': "INTEGER DEFAULT 0",
            'birthdate': "TEXT",
            'address': "TEXT",
            'created_at': "INTEGER",
            'updated_at': "INTEGER DEFAULT 0",
        }
        for col, ddl in wanted.items():
            if col not in have:
                conn.execute(sa.text(f"ALTER TABLE users ADD COLUMN {col} {ddl}"))
    except Exception:
        # Keep migration resilient
        pass

    # Ensure api_usage table
    try:
        res2 = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='api_usage'"))
        if not res2.fetchone():
            conn.execute(sa.text(
                """
                CREATE TABLE api_usage (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  date TEXT NOT NULL,
                  count INTEGER NOT NULL DEFAULT 0
                )
                """
            ))
            conn.execute(sa.text("CREATE UNIQUE INDEX idx_api_usage_user_date ON api_usage(user_id, date)"))
    except Exception:
        pass


def downgrade():
    # Non-destructive; no downgrade to avoid data loss
    pass
