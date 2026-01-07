import pytest


def test_e2e_04_plans_create_and_list(maybe_admin_client):
    if maybe_admin_client is None:
        pytest.skip("No admin configured (set ADMIN_API_TOKEN or E2E_ADMIN_USER/E2E_ADMIN_PASS)")

    create = maybe_admin_client.post(
        "/api/plan",
        json={
            "title": "e2e plan",
            "steps": [{"type": "task", "payload": {"hello": "world"}}],
            "meta": {"e2e": True},
        },
    )
    assert create.status_code == 200, create.text
    cdata = create.json()
    assert cdata.get("ok") is True
    plan = cdata.get("plan") or {}
    assert int(plan.get("id") or 0) > 0

    lst = maybe_admin_client.get("/api/plan", params={"limit": 5, "offset": 0})
    assert lst.status_code == 200, lst.text
    ldata = lst.json()
    assert ldata.get("ok") is True
    assert isinstance(ldata.get("items"), list)

    maybe_admin_client.close()
