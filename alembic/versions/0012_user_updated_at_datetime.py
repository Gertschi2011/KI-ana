"""User: convert users.updated_at to DateTime

Revision ID: 0012_user_updated_at_datetime
Revises: 0011_planner
Create Date: 2026-01-06
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0012_user_updated_at_datetime"
down_revision = "0011_planner"
branch_labels = None
depends_on = None


def _get_column_type_str(inspector: sa.Inspector, table: str, column: str) -> str | None:
    try:
        cols = inspector.get_columns(table)
    except Exception:
        return None
    for c in cols:
        if c.get("name") == column:
            return str(c.get("type") or "")
    return None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    inspector = sa.inspect(bind)

    if dialect != "postgresql":
        # SQLite cannot reliably ALTER COLUMN TYPE; keep this migration Postgres-only.
        return

    type_str = (_get_column_type_str(inspector, "users", "updated_at") or "").lower()
    if "timestamp" in type_str or "datetime" in type_str:
        return

    # Backfill and convert epoch-int -> timestamp.
    # - updated_at > 0: to_timestamp(updated_at)
    # - updated_at == 0 or NULL: use created_at (or NOW if created_at NULL)
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN updated_at TYPE TIMESTAMP
        USING (
          CASE
            WHEN updated_at IS NULL THEN COALESCE(created_at, now())
            WHEN updated_at = 0 THEN COALESCE(created_at, now())
            WHEN updated_at > 0 THEN to_timestamp(updated_at)
            ELSE COALESCE(created_at, now())
          END
        );
        """
    )

    # Align DB default with model default.
    op.execute("ALTER TABLE users ALTER COLUMN updated_at SET DEFAULT now();")


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    inspector = sa.inspect(bind)

    if dialect != "postgresql":
        return

    type_str = (_get_column_type_str(inspector, "users", "updated_at") or "").lower()
    if "int" in type_str or "bigint" in type_str:
        return

    # Convert timestamp -> epoch int (seconds).
    op.execute("ALTER TABLE users ALTER COLUMN updated_at DROP DEFAULT;")
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN updated_at TYPE BIGINT
        USING (
          CASE
            WHEN updated_at IS NULL THEN 0
            ELSE extract(epoch from updated_at)::bigint
          END
        );
        """
    )
    op.execute("ALTER TABLE users ALTER COLUMN updated_at SET DEFAULT 0;")
