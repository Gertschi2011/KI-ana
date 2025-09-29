"""
Add last ack fields to devices

Revision ID: 0009_device_ack_fields
Revises: 0008_device_events_metrics
Create Date: 2025-09-17 16:23:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0009_device_ack_fields'
down_revision = '0008_device_events_metrics'
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table('devices') as batch:
        batch.add_column(sa.Column('last_ack_ts', sa.Integer(), nullable=True, server_default='0'))
        batch.add_column(sa.Column('last_ack_type', sa.String(length=40), nullable=True, server_default=''))
        batch.add_column(sa.Column('last_ack_status', sa.String(length=20), nullable=True, server_default=''))


def downgrade() -> None:
    with op.batch_alter_table('devices') as batch:
        batch.drop_column('last_ack_status')
        batch.drop_column('last_ack_type')
        batch.drop_column('last_ack_ts')

