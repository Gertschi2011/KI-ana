import os
import time
from typing import Dict, Any
from fastapi.testclient import TestClient

os.environ.setdefault("ADMIN_API_TOKEN", "test-admin-token")
from netapi.app import app  # noqa: E402

client = TestClient(app)
AUTH = {"Authorization": f"Bearer {os.environ['ADMIN_API_TOKEN']}"}


def create_plan(title: str, steps: list[Dict[str, Any]]):
    r = client.post("/api/plan", json={"title": title, "steps": steps}, headers=AUTH)
    assert r.status_code == 200, r.text
    j = r.json(); assert j.get("ok") is True
    return int(j["plan"]["id"])


def lease_step():
    r = client.post("/api/plan/lease-step", json={}, headers=AUTH)
    assert r.status_code == 200
    return r.json()


def complete_step(plan_id: int, step_id: int, ok: bool, result: str = "", error: str = ""):
    r = client.post("/api/plan/complete-step", json={
        "plan_id": plan_id,
        "step_id": step_id,
        "ok": ok,
        "result": result,
        "error": error,
    }, headers=AUTH)
    assert r.status_code == 200
    j = r.json(); assert j.get("ok") is True


def get_plan(plan_id: int):
    r = client.get(f"/api/plan/{plan_id}", headers=AUTH)
    assert r.status_code == 200
    return r.json()["plan"]


def test_cancel_retry_flow():
    pid = create_plan(f"CR {time.time()}", [
        {"type": "task", "payload": {"text": "one"}},
        {"type": "sleep", "payload": {"seconds": 0.01}},
    ])
    # Cancel right away
    r = client.post(f"/api/plan/{pid}/cancel", headers=AUTH)
    assert r.status_code == 200
    # Retry should reset to queued
    r2 = client.post(f"/api/plan/{pid}/retry", headers=AUTH)
    assert r2.status_code == 200
    p = get_plan(pid)
    assert p["status"] in {"queued", "running"}

    # Lease all steps and complete them
    seen = set()
    for _ in range(3):
        j = lease_step()
        step = j.get("step")
        if not step:
            break
        if int(step.get("plan_id")) != pid:
            # Complete foreign step so queue isn't stuck
            complete_step(int(step["plan_id"]), int(step["id"]), True, "ok")
            continue
        if step["id"] in seen:
            break
        seen.add(step["id"])  # type: ignore
        complete_step(pid, int(step["id"]), True, "ok")

    # After completion, plan should approach done (depending on worker state)
    p2 = get_plan(pid)
    assert p2["status"] in {"queued", "running", "done"}


def test_multi_executor_simulation():
    # Build a plan using different step types; we simulate worker by completing immediately
    steps = [
        {"type": "knowledge_add", "payload": {"content": "Hello KB", "tags": ["auto","test"], "source": "test:sim"}},
        {"type": "knowledge_search", "payload": {"q": "Hello", "limit": 2}},
        {"type": "os_notify", "payload": {"text": "Planner says hi", "title": "Test"}},
        {"type": "sleep", "payload": {"seconds": 0.01}},
    ]
    pid = create_plan(f"SIM {time.time()}", steps)

    # Lease and complete our steps sequentially (simulate worker)
    completed = 0
    for _ in range(6):
        j = lease_step()
        step = j.get("step")
        if not step:
            break
        if int(step.get("plan_id")) != pid:
            # keep queue healthy
            complete_step(int(step["plan_id"]), int(step["id"]), True, "ok")
            continue
        complete_step(pid, int(step["id"]), True, f"sim:{step.get('type')}")
        completed += 1
    assert completed >= 2

    # Final status should be moving forward
    p = get_plan(pid)
    assert p["status"] in {"queued", "running", "done"}
