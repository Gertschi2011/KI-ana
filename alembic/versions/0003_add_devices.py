"""
Create devices table for Papa OS device management.

Revision ID: 0003_add_devices
Revises: 0002_browser_errors
Create Date: 2025-09-14
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003_add_devices'
down_revision = '0002_browser_errors'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    try:
        tables = set(inspector.get_table_names())
    except Exception:
        tables = set()

    if "devices" in tables:
        return

    # Create minimal base schema; later migrations add additional fields.
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, server_default=sa.text("''")),
        sa.Column("os", sa.String(length=60), nullable=False, server_default=sa.text("''")),
        sa.Column("owner_id", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("last_seen", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("idx_devices_owner", "devices", ["owner_id"], unique=False)
    op.create_index("idx_devices_last_seen", "devices", ["last_seen"], unique=False)


def downgrade():
    pass
