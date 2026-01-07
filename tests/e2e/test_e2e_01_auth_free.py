def test_e2e_01_auth_free_register_verify_login_account(verified_user_session):
    user, client = verified_user_session

    # /api/account is an alias to /api/me
    resp = client.get("/api/account")
    assert resp.status_code == 200
    data = resp.json()

    assert data.get("auth") is True
    u = data.get("user") or {}
    assert u.get("username") == user.username
    assert isinstance(u.get("roles"), list)
    assert u.get("plan") in {"free", "creator", "pro", "team"}
