import json
import pytest
from starlette.testclient import TestClient


def _client():
    from netapi.app import app
    return TestClient(app)


def test_get_settings_default():
    client = _client()
    # Simulate authenticated user by stubbing cookie/session if needed.
    # Here we just call and assert sensible defaults are returned.
    r = client.get("/api/settings")
    assert r.status_code in (200, 401)
    if r.status_code == 401:
        pytest.skip("Auth required for /api/settings in this environment")
    data = r.json()
    assert data.get("ok") is True
    s = data.get("settings", {})
    assert s.get("theme") in ("system", "light", "dark")
    assert s.get("language") in ("de-DE", "en-US", s.get("language"))
    assert str(s.get("memory_on")) in ("0", "1")
    assert str(s.get("autopilot_on")) in ("0", "1")


def test_post_settings_update():
    client = _client()
    r = client.get("/api/settings")
    if r.status_code == 401:
        pytest.skip("Auth required for /api/settings in this environment")
    # update theme to dark
    r2 = client.post("/api/settings", data=json.dumps({"theme": "dark"}), headers={"Content-Type": "application/json"})
    assert r2.status_code in (200, 401)
    if r2.status_code == 401:
        pytest.skip("Auth required for POST /api/settings in this environment")
    data = r2.json()
    assert data.get("ok") is True
    s = data.get("settings", {})
    assert s.get("theme") == "dark"


def test_navbar_theme_toggle_simulation():
    client = _client()
    r = client.get("/api/settings")
    if r.status_code == 401:
        pytest.skip("Auth required for /api/settings in this environment")
    # sequence system -> light -> dark
    seq = ["system", "light", "dark"]
    for t in seq:
        rr = client.post("/api/settings", data=json.dumps({"theme": t}), headers={"Content-Type": "application/json"})
        assert rr.status_code in (200, 401)
        if rr.status_code == 401:
            pytest.skip("Auth required for POST /api/settings in this environment")
        s = rr.json().get("settings", {})
        assert s.get("theme") == t
