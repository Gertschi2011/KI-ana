import os
import time
from typing import Dict, Any

from fastapi.testclient import TestClient

# Use ADMIN_API_TOKEN shortcut for creator access
os.environ.setdefault("ADMIN_API_TOKEN", "test-admin-token")

from netapi.app import app  # noqa: E402

client = TestClient(app)
AUTH = {"Authorization": f"Bearer {os.environ['ADMIN_API_TOKEN']}"}


def _create_plan(title: str, steps: list[Dict[str, Any]]):
    r = client.post("/api/plan", json={"title": title, "steps": steps}, headers=AUTH)
    assert r.status_code == 200, r.text
    j = r.json(); assert j.get("ok") is True
    pid = int(j["plan"]["id"])
    return pid, j["plan"]


def test_create_list_count_duplicate_flow():
    title = f"Test Plan {int(time.time())}"
    steps = [
        {"type": "task", "payload": {"text": "hello"}},
        {"type": "sleep", "payload": {"seconds": 0.1}},
    ]
    pid, plan = _create_plan(title, steps)

    # List
    r = client.get("/api/plan?limit=10", headers=AUTH)
    assert r.status_code == 200
    j = r.json(); assert j.get("ok") is True
    items = j.get("items") or []
    assert any(int(p.get("id")) == pid for p in items)

    # Count endpoint
    r2 = client.get("/api/plan/count", headers=AUTH)
    assert r2.status_code == 200
    jc = r2.json(); assert jc.get("ok") is True
    assert isinstance(jc.get("total"), int)
    assert isinstance(jc.get("by_status"), dict)

    # Duplicate
    r3 = client.post(f"/api/plan/{pid}/duplicate", headers=AUTH)
    assert r3.status_code == 200
    jd = r3.json(); assert jd.get("ok") is True
    dup = jd.get("plan") or {}
    assert dup.get("title", "").endswith("(copy)")


def test_lease_and_complete_step():
    # Create a small plan with one step to lease
    title = f"Lease Flow {int(time.time())}"
    steps = [{"type": "task", "payload": {"text": "lease-me"}}]
    pid, plan = _create_plan(title, steps)

    # Lease a step
    r = client.post("/api/plan/lease-step", json={}, headers=AUTH)
    assert r.status_code == 200
    j = r.json(); assert j.get("ok") is True
    step = j.get("step")
    assert step and int(step.get("plan_id")) == pid

    # Complete the step
    r2 = client.post("/api/plan/complete-step", json={
        "plan_id": int(step["plan_id"]),
        "step_id": int(step["id"]),
        "ok": True,
        "result": "ack",
        "error": ""
    }, headers=AUTH)
    assert r2.status_code == 200
    j2 = r2.json(); assert j2.get("ok") is True
