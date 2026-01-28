from fastapi.testclient import TestClient

from netapi.app import app


client = TestClient(app)


def test_chat_selftalk_was_machst_du_no_web_no_scaffold():
    r = client.post("/api/chat", json={"message": "was machst du?", "stream": False})
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True

    reply = str(data.get("reply") or "")
    assert reply.strip()

    low = reply.lower()
    assert ("ki_ana" in reply) or ("ich helfe" in low) or ("begleiter" in low)
    assert "wikipedia.org" not in low
    assert "hier ist, was ich zu" not in low
    assert "kernpunkte:" not in low

    explain = data.get("explain") or {}
    policy = (explain.get("policy") or {}) if isinstance(explain, dict) else {}
    assert policy.get("web_ok") is False

    # DoD: no default style prompt on selftalk
    assert (data.get("style_prompt") in (None, ""))


def test_chat_hello_no_scaffold_or_empty_kernpunkte():
    r = client.post("/api/chat", json={"message": "hallo", "stream": False})
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True

    reply = str(data.get("reply") or "")
    low = reply.lower()
    assert reply.strip()
    assert "hier ist, was ich zu" not in low
    assert "kernpunkte:" not in low
