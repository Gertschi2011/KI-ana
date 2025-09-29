"""
Create admin_audit table for admin action logging.

Revision ID: 0004_admin_audit
Revises: 0003_add_devices
Create Date: 2025-09-14
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004_admin_audit'
down_revision = '0003_add_devices'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    try:
        res = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_audit'"))
        if not res.fetchone():
            conn.execute(sa.text(
                """
                CREATE TABLE admin_audit (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts INTEGER DEFAULT 0,
                  actor_user_id INTEGER DEFAULT 0,
                  action TEXT DEFAULT '',
                  target_type TEXT DEFAULT '',
                  target_id INTEGER DEFAULT 0,
                  meta TEXT DEFAULT '{}'
                )
                """
            ))
            conn.execute(sa.text("CREATE INDEX idx_admin_audit_ts ON admin_audit(ts)"))
            conn.execute(sa.text("CREATE INDEX idx_admin_audit_actor ON admin_audit(actor_user_id)"))
            conn.execute(sa.text("CREATE INDEX idx_admin_audit_target ON admin_audit(target_id)"))
    except Exception:
        pass


def downgrade():
    pass
