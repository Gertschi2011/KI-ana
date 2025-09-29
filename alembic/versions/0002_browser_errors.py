"""
Add browser_errors table for client telemetry.

Revision ID: 0002_browser_errors
Revises: 0001_initial_schema
Create Date: 2025-09-14
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_browser_errors'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    try:
        res = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='browser_errors'"))
        if not res.fetchone():
            conn.execute(sa.text(
                """
                CREATE TABLE browser_errors (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts INTEGER DEFAULT 0,
                  level TEXT DEFAULT 'error',
                  message TEXT DEFAULT '',
                  url TEXT DEFAULT '',
                  stack TEXT DEFAULT '',
                  user_id INTEGER DEFAULT 0,
                  user_agent TEXT DEFAULT '',
                  ip TEXT DEFAULT '',
                  count INTEGER DEFAULT 1
                )
                """
            ))
            conn.execute(sa.text("CREATE INDEX idx_browser_errors_ts ON browser_errors(ts)"))
            conn.execute(sa.text("CREATE INDEX idx_browser_errors_ip ON browser_errors(ip)"))
            conn.execute(sa.text("CREATE INDEX idx_browser_errors_user ON browser_errors(user_id)"))
    except Exception:
        pass


def downgrade():
    pass
