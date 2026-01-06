"""
Add user location fields (street/postal_code/city/country_code)

Revision ID: 0012_user_location_fields
Revises: 0011_planner
Create Date: 2025-11-26 10:00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0012_user_location_fields"
down_revision = "0011_planner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("street", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("postal_code", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("city", sa.String(length=200), nullable=True))
    op.add_column("users", sa.Column("country_code", sa.String(length=2), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "country_code")
    op.drop_column("users", "city")
    op.drop_column("users", "postal_code")
    op.drop_column("users", "street")
