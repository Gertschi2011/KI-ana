def test_e2e_90_account_unauth_is_auth_false(http):
    resp = http.get("/api/account")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("auth") is False
    assert data.get("user") is None


def test_e2e_90_verify_email_invalid_token(http):
    resp = http.post("/api/verify-email", json={"token": "not-a-real-token"})
    assert resp.status_code == 400


def test_e2e_90_login_wrong_password(http):
    # Should not 500; either 401 or 400 depending on validation.
    resp = http.post("/api/login", json={"username": "no_such_user", "password": "wrong"})
    assert resp.status_code in {400, 401}
