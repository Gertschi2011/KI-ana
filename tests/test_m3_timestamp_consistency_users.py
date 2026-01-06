import os

import pytest
import sqlalchemy as sa

from netapi.models import User


def test_user_model_created_at_and_updated_at_are_datetime() -> None:
    assert isinstance(User.__table__.c.created_at.type, sa.DateTime)
    assert isinstance(User.__table__.c.updated_at.type, sa.DateTime)


def test_users_table_columns_match_model_on_postgres() -> None:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        pytest.skip("DATABASE_URL not set")

    if "postgres" not in url:
        pytest.skip("DB type is not postgres")

    engine = sa.create_engine(url)
    insp = sa.inspect(engine)

    cols = {c["name"]: c for c in insp.get_columns("users")}
    assert "created_at" in cols
    assert "updated_at" in cols

    def _is_timestamp(col: str) -> bool:
        t = cols[col]["type"]
        s = str(t).lower()
        return ("timestamp" in s) or ("datetime" in s)

    assert _is_timestamp("created_at")
    assert _is_timestamp("updated_at")
