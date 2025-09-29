import os
import sys
from pathlib import Path
import sqlite3
import pytest
import anyio

# Ensure project root is on sys.path as early as possible (import time)
try:
    _PROJ_ROOT = Path(__file__).resolve().parents[1]
    if str(_PROJ_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJ_ROOT))
except Exception:
    pass

# Ensure Test Mode for streaming and planner reset behavior
@pytest.fixture(autouse=True)
def _test_mode_env(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")
    # Make sure PYTHONPATH logic in tests works fine
    monkeypatch.setenv("KI_ROOT", os.getenv("KI_ROOT", os.path.expanduser("~/ki_ana")))
    # Ensure sse_starlette AppStatus event belongs to the active loop (avoid cross-loop RuntimeError)
    try:
        from sse_starlette.sse import AppStatus  # type: ignore
        # Re-create event within current test loop
        AppStatus.should_exit_event = anyio.Event()
    except Exception:
        pass
    yield


def _db_path_from_env() -> str:
    db_url = os.getenv("DATABASE_URL", "sqlite:///db.sqlite3")
    try:
        if db_url.startswith("sqlite:///"):
            return os.path.expanduser(db_url[len("sqlite///"):])
        if db_url.startswith("sqlite://"):
            return os.path.expanduser(db_url[len("sqlite://"):])
        return os.path.expanduser(db_url)
    except Exception:
        return "db.sqlite3"


@pytest.fixture(autouse=True)
def _reset_state_before_each_test():
    # Reset planner tables (best-effort)
    try:
        from netapi.modules.plan.router import clear_plan_state
        clear_plan_state()
    except Exception:
        pass

    # Reset knowledge_blocks table (best-effort)
    try:
        db_path = _db_path_from_env()
        if db_path:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                try:
                    cur.execute("DELETE FROM knowledge_blocks")
                except Exception:
                    pass
                conn.commit()
    except Exception:
        pass
    yield
