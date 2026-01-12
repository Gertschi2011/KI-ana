"""Convert audit_events.meta to JSONB (Postgres)

Revision ID: 0015_audit_events_meta_jsonb
Revises: 0014_audit_events
Create Date: 2026-01-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_audit_events_meta_jsonb"
down_revision = "0014_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind is None:
        return

    if bind.dialect.name != "postgresql":
        # SQLite/dev: keep TEXT (JSON operators not supported anyway)
        return

    # Ensure no NULLs before type conversion
    op.execute("UPDATE audit_events SET meta = '{}' WHERE meta IS NULL")

    # Postgres cannot always auto-cast an existing TEXT default to JSONB during
    # ALTER COLUMN TYPE, so drop it first.
    op.execute("ALTER TABLE audit_events ALTER COLUMN meta DROP DEFAULT")

    # Convert TEXT -> JSONB. Existing meta is JSON-stringified dicts.
    op.execute("ALTER TABLE audit_events ALTER COLUMN meta TYPE JSONB USING meta::jsonb")
    op.execute("ALTER TABLE audit_events ALTER COLUMN meta SET DEFAULT '{}'::jsonb")


def downgrade() -> None:
    bind = op.get_bind()
    if bind is None:
        return

    if bind.dialect.name != "postgresql":
        return

    op.execute("ALTER TABLE audit_events ALTER COLUMN meta TYPE TEXT USING meta::text")
    op.execute("ALTER TABLE audit_events ALTER COLUMN meta SET DEFAULT '{}'")
