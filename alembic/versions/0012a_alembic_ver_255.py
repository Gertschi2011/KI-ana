"""Postgres: widen alembic_version.version_num to VARCHAR(255)

This repository uses human-readable revision IDs like
"0013_add_folder_id_to_conversations" (> 32 chars).

Alembic's default version table uses VARCHAR(32) which can cause fresh
Postgres upgrades to fail once it tries to stamp a long revision.

We insert this short-ID migration before the first long revision so it can
run even when version_num is still VARCHAR(32).

Revision ID: 0012a_alembic_ver_255
Revises: 0012_user_updated_at_datetime
Create Date: 2026-01-12
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "0012a_alembic_ver_255"
down_revision = "0012_user_updated_at_datetime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind is None:
        return

    if bind.dialect.name != "postgresql":
        return

    # Safe for existing DBs; Postgres allows widening VARCHAR without rewriting data.
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)")


def downgrade() -> None:
    bind = op.get_bind()
    if bind is None:
        return

    if bind.dialect.name != "postgresql":
        return

    # Best-effort; keep at least 32 to match Alembic default.
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(32)")
