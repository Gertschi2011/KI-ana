"""
Add device_events table for per-device event queue

Revision ID: 0007_device_events
Revises: 0006_device_tokens
Create Date: 2025-09-17 14:53:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0007_device_events'
down_revision = '0006_device_tokens'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'device_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('device_id', sa.Integer(), nullable=False, index=True),
        sa.Column('ts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('type', sa.String(length=40), nullable=False, server_default='message'),
        sa.Column('payload', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('delivered_at', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_table('device_events')
