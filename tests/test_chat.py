import os
import time
from fastapi.testclient import TestClient

from netapi.app import app
from netapi.agent.agent import run_agent

client = TestClient(app)


def test_chat_calc_sync():
    r = client.post("/api/chat", json={"message": "2+2"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert data.get("ok") is True
    assert isinstance(data.get("reply"), str)
    assert data["reply"] != ""
    # Either explicit math phrase or contains the result
    assert ("Rechnung" in data["reply"]) or ("4" in data["reply"])  # tolerant


def test_chat_smalltalk_sync():
    r = client.post("/api/chat", json={"message": "Hi, wie gehts?"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert isinstance(data.get("reply"), str)
    assert data["reply"] != ""


def test_stream_endpoint_available():
    # We don't parse the SSE stream here; just ensure endpoint exists and responds 200
    r = client.get("/api/chat/stream", params={"message": "Hallo"})
    assert r.status_code == 200
    # Content-Type may be event-stream or json depending on availability
    ctype = r.headers.get("content-type", "")
    assert ("event-stream" in ctype) or ("application/json" in ctype) or ("text/plain" in ctype)


def test_agent_fallback_not_looping():
    # Disable web to exercise non-web fallback diversity
    os.environ["ALLOW_NET"] = "0"
    msg = "Erzähl mal irgendwas ohne Details"
    out1 = run_agent(msg, persona="friendly", lang="de-DE", conv_id="t_loop").get("reply", "")
    assert isinstance(out1, str)
    assert out1 != ""
    # Immediate second call should not repeat the identical clarify phrase due to cooldown guard
    out2 = run_agent(msg, persona="friendly", lang="de-DE", conv_id="t_loop").get("reply", "")
    assert isinstance(out2, str)
    assert out2 != ""
    assert out2 != out1  # should differ due to cooldown-driven alternative response
