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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("devices")}

    with op.batch_alter_table('devices') as batch:
        if "token_hash" not in existing_cols:
            batch.add_column(sa.Column('token_hash', sa.String(length=128), nullable=True))
        if "token_hint" not in existing_cols:
            batch.add_column(sa.Column('token_hint', sa.String(length=16), nullable=True))
        if "issued_at" not in existing_cols:
            batch.add_column(sa.Column('issued_at', sa.Integer(), nullable=True))
        if "last_auth_at" not in existing_cols:
            batch.add_column(sa.Column('last_auth_at', sa.Integer(), nullable=True))
        if "revoked_at" not in existing_cols:
            batch.add_column(sa.Column('revoked_at', sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("devices")}

    with op.batch_alter_table('devices') as batch:
        if "revoked_at" in existing_cols:
            batch.drop_column('revoked_at')
        if "last_auth_at" in existing_cols:
            batch.drop_column('last_auth_at')
        if "issued_at" in existing_cols:
            batch.drop_column('issued_at')
        if "token_hint" in existing_cols:
            batch.drop_column('token_hint')
        if "token_hash" in existing_cols:
            batch.drop_column('token_hash')
