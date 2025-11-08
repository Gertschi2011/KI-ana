from fastapi.testclient import TestClient
from netapi.app import app

client = TestClient(app)

def test_timeflow_endpoint_smoke():
    r = client.get("/api/system/timeflow")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    tf = data.get("timeflow", {})
    # Keys exist (best-effort)
    assert "tick" in tf
    assert "subjective_time" in tf
    assert "activation" in tf
    # HTTP request rate metrics present
    assert "reqs_last_window" in tf
    assert "reqs_per_min" in tf
