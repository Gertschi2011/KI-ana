"""Add audit_events (append-only) table

SQLite-safe + deterministic for CI.

Revision ID: 0014_audit_events
Revises: 0013_add_folder_id_to_conversations
Create Date: 2026-01-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0014_audit_events"
down_revision = "0013_add_folder_id_to_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    try:
        tables = set(inspector.get_table_names())
    except Exception:
        tables = set()

    if "audit_events" in tables:
        return

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actor_type", sa.String(length=16), nullable=False, server_default=sa.text("'system'")),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False, server_default=sa.text("''")),
        sa.Column("subject_type", sa.String(length=64), nullable=False, server_default=sa.text("''")),
        sa.Column("subject_id", sa.String(length=128), nullable=True),
        sa.Column("result", sa.String(length=16), nullable=False, server_default=sa.text("'success'")),
        sa.Column("meta", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
    )

    op.create_index("ix_audit_events_ts", "audit_events", ["ts"], unique=False)
    op.create_index("ix_audit_events_action_ts", "audit_events", ["action", "ts"], unique=False)
    op.create_index("ix_audit_events_actor_id_ts", "audit_events", ["actor_id", "ts"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    try:
        tables = set(inspector.get_table_names())
    except Exception:
        tables = set()

    if "audit_events" not in tables:
        return

    try:
        op.drop_index("ix_audit_events_actor_id_ts", table_name="audit_events")
    except Exception:
        pass
    try:
        op.drop_index("ix_audit_events_action_ts", table_name="audit_events")
    except Exception:
        pass
    try:
        op.drop_index("ix_audit_events_ts", table_name="audit_events")
    except Exception:
        pass

    op.drop_table("audit_events")
