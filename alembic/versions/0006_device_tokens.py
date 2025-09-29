"""
Add device token fields

Revision ID: 0006_device_tokens
Revises: 0005_user_status_fields
Create Date: 2025-09-17 13:55:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0006_device_tokens'
down_revision = '0005_user_status_fields'
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table('devices') as batch:
        batch.add_column(sa.Column('token_hash', sa.String(length=128), nullable=True))
        batch.add_column(sa.Column('token_hint', sa.String(length=16), nullable=True))
        batch.add_column(sa.Column('issued_at', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('last_auth_at', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('revoked_at', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('devices') as batch:
        batch.drop_column('revoked_at')
        batch.drop_column('last_auth_at')
        batch.drop_column('issued_at')
        batch.drop_column('token_hint')
        batch.drop_column('token_hash')
