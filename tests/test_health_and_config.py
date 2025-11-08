import os
from fastapi.testclient import TestClient

# Ensure app imports without side-effects causing failures in tests
from netapi.app import app

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_system_config():
    # Provide defaults if env not set in test runner
    os.environ.setdefault("FREE_DAILY_QUOTA", "20")
    os.environ.setdefault("KI_UPGRADE_URL", "/static/upgrade.html")
    r = client.get("/api/system/config")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert isinstance(data.get("free_daily_quota"), int)
    assert isinstance(data.get("upgrade_url"), str)
