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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("devices")}

    with op.batch_alter_table('devices') as batch:
        if "last_ack_ts" not in existing_cols:
            batch.add_column(sa.Column('last_ack_ts', sa.Integer(), nullable=True, server_default='0'))
        if "last_ack_type" not in existing_cols:
            batch.add_column(sa.Column('last_ack_type', sa.String(length=40), nullable=True, server_default=''))
        if "last_ack_status" not in existing_cols:
            batch.add_column(sa.Column('last_ack_status', sa.String(length=20), nullable=True, server_default=''))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("devices")}

    with op.batch_alter_table('devices') as batch:
        if "last_ack_status" in existing_cols:
            batch.drop_column('last_ack_status')
        if "last_ack_type" in existing_cols:
            batch.drop_column('last_ack_type')
        if "last_ack_ts" in existing_cols:
            batch.drop_column('last_ack_ts')

