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

    dialect = getattr(getattr(conn, "dialect", None), "name", None)

    # --- Postgres / non-SQLite ------------------------------------------------
    # Historically, early migrations were SQLite-only (sqlite_master/PRAGMA).
    # For fresh Postgres DBs, we must at least create baseline tables that later
    # migrations ALTER (e.g. users in 0012_user_location_fields).
    if dialect != "sqlite":
        inspector = sa.inspect(conn)
        try:
            tables = set(inspector.get_table_names())
        except Exception:
            tables = set()

        if "users" not in tables:
            # Keep this minimal: later migrations add extra columns.
            is_papa_default = sa.text("false") if dialect == "postgresql" else sa.text("0")
            now_default = sa.text("now()") if dialect == "postgresql" else None

            op.create_table(
                "users",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("username", sa.String(length=255), nullable=True, unique=True),
                sa.Column("email", sa.String(length=255), nullable=True, unique=True),
                sa.Column("password_hash", sa.Text(), nullable=True),
                sa.Column("birthdate", sa.String(length=64), nullable=True),
                sa.Column("address", sa.Text(), nullable=True),
                sa.Column("role", sa.String(length=32), nullable=True, server_default=sa.text("'user'"), quote=True),
                sa.Column("tier", sa.String(length=32), nullable=True, server_default=sa.text("'user'")),
                sa.Column("is_papa", sa.Boolean(), nullable=True, server_default=is_papa_default),
                sa.Column("daily_quota", sa.Integer(), nullable=True, server_default=sa.text("20")),
                sa.Column("quota_reset_at", sa.Integer(), nullable=True, server_default=sa.text("0")),
                sa.Column("plan", sa.String(length=32), nullable=True, server_default=sa.text("'free'")),
                sa.Column("plan_until", sa.Integer(), nullable=True, server_default=sa.text("0")),
                sa.Column("created_at", sa.DateTime(), nullable=True, server_default=now_default),
                sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=now_default),
            )

        if "api_usage" not in tables:
            op.create_table(
                "api_usage",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("user_id", sa.Integer(), nullable=False),
                sa.Column("date", sa.String(length=32), nullable=False),
                sa.Column("count", sa.Integer(), nullable=False, server_default=sa.text("0")),
                sa.UniqueConstraint("user_id", "date", name="idx_api_usage_user_date"),
            )

        return

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
