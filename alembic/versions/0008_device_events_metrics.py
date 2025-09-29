"""
Add events_pruned_total to devices for queue retention metrics

Revision ID: 0008_device_events_metrics
Revises: 0007_device_events
Create Date: 2025-09-17 16:02:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0008_device_events_metrics'
down_revision = '0007_device_events'
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table('devices') as batch:
        batch.add_column(sa.Column('events_pruned_total', sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('devices') as batch:
        batch.drop_column('events_pruned_total')

