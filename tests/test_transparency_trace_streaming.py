import json


def _extract_finalize_from_sse_lines(lines):
    for raw in lines:
        if raw is None:
            continue
        if isinstance(raw, (bytes, bytearray)):
            try:
                line = raw.decode("utf-8", errors="ignore")
            except Exception:
                continue
        else:
            line = str(raw)
        line = line.strip("\r\n")
        if not line.startswith("data: "):
            continue
        try:
            obj = json.loads(line[6:])
        except Exception:
            continue
        if obj.get("type") == "finalize":
            return obj
    return None


def test_streaming_finalize_includes_msg_id_and_trace_roundtrip():
    from netapi.app import app
    from starlette.testclient import TestClient
    from netapi.deps import get_current_user_opt, get_current_user_required
    from netapi.db import SessionLocal
    from netapi.models import User

    client = TestClient(app)

    paid_user = {"id": 4242, "role": "user", "roles": ["user"], "plan": "pro", "country_code": "AT"}

    def _paid():
        return paid_user

    app.dependency_overrides[get_current_user_opt] = _paid
    app.dependency_overrides[get_current_user_required] = _paid

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == int(paid_user["id"])).first()
        if not u:
            u = User(id=int(paid_user["id"]), username="test_paid_stream", email="test_paid_stream@example.com", plan="pro")
            db.add(u)
        else:
            u.plan = "pro"
        db.commit()
    finally:
        try:
            db.close()
        except Exception:
            pass

    # Streaming request (keep deterministic: no web)
    with client.stream(
        "GET",
        "/api/chat/stream",
        params={
            "message": "nenne mir die aktuellen inflationszahlen in AT",
            "persona": "friendly",
            "lang": "de-DE",
            "web_ok": "false",
        },
    ) as r:
        assert r.status_code == 200
        final = _extract_finalize_from_sse_lines(r.iter_lines())

    assert isinstance(final, dict)
    assert final.get("type") == "finalize"

    conv_id = final.get("conv_id") or final.get("conversation_id")
    msg_id = final.get("msg_id")

    assert conv_id is not None
    assert msg_id is not None

    tr = client.get("/api/chat/trace", params={"conv_id": int(conv_id), "msg_id": int(msg_id), "include_memory_preview": False})
    assert tr.status_code == 200
    j = tr.json()

    assert j.get("ok") is True
    assert j.get("conv_id") == int(conv_id)
    assert j.get("msg_id") == int(msg_id)
    assert isinstance(j.get("trace"), dict)
    assert isinstance(j["trace"].get("sources"), list)
    assert isinstance(j["trace"].get("memory_ids"), list)
