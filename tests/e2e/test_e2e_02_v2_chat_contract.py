def test_e2e_02_v2_chat_contract_fields(verified_user_session):
    _user, client = verified_user_session

    resp = client.post("/api/v2/chat", json={"message": "ping"})
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Stable contract: reply/meta/sources/trace must exist with correct types.
    assert isinstance(data.get("ok"), bool)
    assert isinstance(data.get("reply"), str)
    assert isinstance(data.get("meta"), dict)
    assert isinstance(data.get("sources"), list)
    assert isinstance(data.get("trace"), list)
