"""Add conversations.folder_id (SQLite-safe)

CI runs E2E against SQLite and expects the schema to match models.
This migration is defensive:
- If the table doesn't exist yet, it skips (app init_db will create it).
- If the column already exists, it skips.

Revision ID: 0013_add_folder_id_to_conversations
Revises: 0012_user_updated_at_datetime
Create Date: 2026-01-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0013_add_folder_id_to_conversations"
down_revision = "0012a_alembic_ver_255"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    try:
        tables = set(inspector.get_table_names())
    except Exception:
        tables = set()

    # If the table does not exist yet, create it now so CI is deterministic
    # (E2E runs migrations before app init).
    if "conversations" not in tables:
        op.create_table(
            "conversations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=True),
            sa.Column("created_at", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("updated_at", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("folder_id", sa.Integer(), nullable=True),
        )
        op.create_index(
            "ix_conversations_user_id",
            "conversations",
            ["user_id"],
            unique=False,
        )
        op.create_index(
            "ix_conversations_folder_id",
            "conversations",
            ["folder_id"],
            unique=False,
        )
        return

    try:
        cols = inspector.get_columns("conversations")
        have = {c.get("name") for c in cols}
    except Exception:
        have = set()

    if "folder_id" in have:
        return

    op.add_column(
        "conversations",
        sa.Column("folder_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_conversations_folder_id",
        "conversations",
        ["folder_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    try:
        tables = set(inspector.get_table_names())
    except Exception:
        tables = set()

    if "conversations" not in tables:
        return

    try:
        cols = inspector.get_columns("conversations")
        have = {c.get("name") for c in cols}
    except Exception:
        have = set()

    if "folder_id" not in have:
        return

    try:
        op.drop_index("ix_conversations_folder_id", table_name="conversations")
    except Exception:
        pass

    try:
        op.drop_column("conversations", "folder_id")
    except Exception:
        # SQLite may not support DROP COLUMN depending on version.
        pass
