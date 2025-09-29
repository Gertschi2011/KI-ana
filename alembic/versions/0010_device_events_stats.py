"""
Create device_events_stats rollup table

Revision ID: 0010_device_events_stats
Revises: 0009_device_ack_fields
Create Date: 2025-09-17 17:21:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0010_device_events_stats'
down_revision = '0009_device_ack_fields'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'device_events_stats',
        sa.Column('ts_hour', sa.Integer(), primary_key=True),  # Unix epoch, truncated to the hour
        sa.Column('queued_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pruned_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_table('device_events_stats')
