"""
Add user lifecycle fields: status, suspended_reason, deleted_at

Revision ID: 0005_user_status_fields
Revises: 0004_admin_audit
Create Date: 2025-09-14
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0005_user_status_fields'
down_revision = '0004_admin_audit'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    try:
        # Ensure columns exist (SQLite-safe ADD COLUMN)
        cols = conn.execute(sa.text("PRAGMA table_info(users)")).fetchall()
        have = {c[1] for c in cols}
        adds = []
        if 'status' not in have:
            adds.append("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
        if 'suspended_reason' not in have:
            adds.append("ALTER TABLE users ADD COLUMN suspended_reason TEXT DEFAULT ''")
        if 'deleted_at' not in have:
            adds.append("ALTER TABLE users ADD COLUMN deleted_at INTEGER DEFAULT 0")
        for stmt in adds:
            conn.execute(sa.text(stmt))
    except Exception:
        pass


def downgrade():
    # No destructive downgrade to avoid data loss
    pass
