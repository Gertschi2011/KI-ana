import pytest


def test_e2e_03_rbac_admin_users_denies_anonymous(http):
    resp = http.get("/api/admin/users")
    assert resp.status_code in {401, 403}, resp.text


def test_e2e_03_rbac_admin_users_denies_normal_user(verified_user_session):
    _user, client = verified_user_session
    resp = client.get("/api/admin/users")
    assert resp.status_code == 403, resp.text


def test_e2e_03_rbac_admin_users_allows_creator(maybe_admin_client):
    if maybe_admin_client is None:
        pytest.skip("No admin configured (set ADMIN_API_TOKEN or E2E_ADMIN_USER/E2E_ADMIN_PASS)")

    resp = maybe_admin_client.get("/api/admin/users")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("ok") is True
    assert isinstance(data.get("items"), list)

    maybe_admin_client.close()
