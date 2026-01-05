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
    conn = op.get_bind()
    if getattr(getattr(conn, "dialect", None), "name", None) != "sqlite":
        return
    try:
        res = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'"))
        if not res.fetchone():
            conn.execute(sa.text(
                """
                CREATE TABLE devices (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT DEFAULT '',
                  os TEXT DEFAULT '',
                  owner_id INTEGER DEFAULT 0,
                  status TEXT DEFAULT 'unknown',
                  last_seen INTEGER DEFAULT 0,
                  created_at INTEGER DEFAULT 0,
                  updated_at INTEGER DEFAULT 0
                )
                """
            ))
            conn.execute(sa.text("CREATE INDEX idx_devices_owner ON devices(owner_id)"))
            conn.execute(sa.text("CREATE INDEX idx_devices_last_seen ON devices(last_seen)"))
    except Exception:
        pass


def downgrade():
    pass
