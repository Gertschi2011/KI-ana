import time


def test_trace_forbidden_for_free_plan():
    from netapi.app import app
    from starlette.testclient import TestClient
    from netapi.deps import get_current_user_required

    client = TestClient(app)

    def _free_user():
        return {
        "id": 1,
        "role": "user",
        "roles": ["user"],
        "plan": "free",
        "country_code": "AT",
        }

    app.dependency_overrides[get_current_user_required] = _free_user

    r = client.get("/api/chat/trace", params={"conv_id": 1, "last": 1})
    assert r.status_code == 403
    j = r.json()
    assert j.get("detail") == "upgrade_required"


def test_trace_roundtrip_for_paid_user_via_chat_once():
    from netapi.app import app
    from starlette.testclient import TestClient
    from netapi.deps import get_current_user_opt, get_current_user_required
    from netapi.db import SessionLocal
    from netapi.models import User

    client = TestClient(app)

    # Paid user
    user = {"id": 1, "role": "user", "roles": ["user"], "plan": "pro", "country_code": "AT"}

    def _paid_user():
        return user

    app.dependency_overrides[get_current_user_opt] = _paid_user
    app.dependency_overrides[get_current_user_required] = _paid_user

    # Make sure the user exists in DB with a paid plan (used by trace persistence gate).
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == int(user["id"])).first()
        if not u:
            u = User(id=int(user["id"]), username="test_paid_user", email="test_paid_user@example.com", plan="pro")
            db.add(u)
        else:
            u.plan = "pro"
        db.commit()
    finally:
        try:
            db.close()
        except Exception:
            pass

    r = client.post(
        "/api/chat",
        json={"message": "Wie geht es dir?", "persona": "friendly", "lang": "de-DE", "conv_id": None, "web_ok": False},
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload.get("conv_id")
    assert payload.get("msg_id")

    tr = client.get(
        "/api/chat/trace",
        params={"conv_id": payload["conv_id"], "last": 1, "include_memory_preview": False},
    )
    assert tr.status_code == 200
    j = tr.json()
    assert j.get("ok") is True
    assert j.get("conv_id") == payload["conv_id"]
    assert j.get("msg_id")
    assert isinstance(j.get("trace"), dict)
    assert isinstance(j["trace"].get("sources"), list)
    assert isinstance(j["trace"].get("memory_ids"), list)


def test_memory_preview_free_forbidden():
    from netapi.app import app
    from starlette.testclient import TestClient
    from netapi.deps import get_current_user_required

    client = TestClient(app)

    def _free_user():
        return {"id": 1, "role": "user", "roles": ["user"], "plan": "free", "country_code": "AT"}

    app.dependency_overrides[get_current_user_required] = _free_user
    r = client.post("/api/memory/preview", json={"ids": ["BLK_DOES_NOT_EXIST"], "limit_chars": 120})
    assert r.status_code == 403
    assert r.json().get("detail") == "upgrade_required"


def test_memory_preview_user_allowed():
    from netapi.app import app
    from starlette.testclient import TestClient
    from netapi.deps import get_current_user_required
    from netapi import memory_store

    client = TestClient(app)

    def _user_paid():
        return {"id": 1, "role": "user", "roles": ["user"], "plan": "pro", "country_code": "AT"}

    app.dependency_overrides[get_current_user_required] = _user_paid

    bid = memory_store.add_block(
        title="Test Block",
        content="Hallo Welt. Dies ist ein Testblock.",
        tags=["test"],
        meta={"topic": "Test/Topic"},
    )

    r = client.post("/api/memory/preview", json={"ids": [bid], "limit_chars": 120})
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert isinstance(j.get("items"), list)
    assert j["items"][0].get("id") == bid
    assert "preview" in j["items"][0]


def test_sources_required_enforced_for_current_query(monkeypatch):
    from netapi.modules.chat.router import _CHAT_EXPLAIN_CTX, _attach_explain_and_kpis

    monkeypatch.setenv("ALLOW_NET", "1")

    # Simulate a question-like request
    _CHAT_EXPLAIN_CTX.set({"cid": "t", "t0": time.time(), "is_question": True, "policy": {"web_ok": True}, "tools": [], "kpi_done": False})

    payload = {"reply": "X", "meta": {"sources": []}, "memory_ids": []}
    out = _attach_explain_and_kpis(
        payload,
        route="/api/chat",
        intent="current_query",
        policy=None,
        tools=None,
        source_expected=True,
        sources_count=0,
    )

    assert "Ich kann das gerade nicht belegen" in (out.get("reply") or "")


def test_sources_required_offline_does_not_hard_refuse(monkeypatch):
    from netapi.modules.chat.router import _CHAT_EXPLAIN_CTX, _attach_explain_and_kpis

    monkeypatch.setenv("ALLOW_NET", "0")
    _CHAT_EXPLAIN_CTX.set({"cid": "t", "t0": time.time(), "is_question": True, "policy": {"web_ok": False}, "tools": [], "kpi_done": False})

    payload = {"reply": "Meine Einschätzung: X.", "meta": {"sources": []}, "memory_ids": []}
    out = _attach_explain_and_kpis(
        payload,
        route="/api/chat",
        intent="news",
        policy=None,
        tools=None,
        source_expected=True,
        sources_count=0,
    )

    # Should keep the original answer and append a disclaimer/question.
    assert (out.get("reply") or "").startswith("Meine Einschätzung")
    assert "keinen Zugriff auf Quellen" in (out.get("reply") or "")


def test_smalltalk_never_enforces_sources(monkeypatch):
    from netapi.modules.chat.router import _CHAT_EXPLAIN_CTX, _attach_explain_and_kpis

    monkeypatch.setenv("ALLOW_NET", "1")
    _CHAT_EXPLAIN_CTX.set({"cid": "t", "t0": time.time(), "is_question": True, "policy": {"web_ok": True}, "tools": [], "kpi_done": False})

    payload = {"reply": "Mir geht's gut!", "meta": {"sources": []}, "memory_ids": []}
    out = _attach_explain_and_kpis(
        payload,
        route="/api/chat",
        intent="smalltalk",
        policy=None,
        tools=None,
        source_expected=True,
        sources_count=0,
    )
    assert out.get("reply") == "Mir geht's gut!"


def test_coding_help_never_enforces_sources(monkeypatch):
    from netapi.modules.chat.router import _CHAT_EXPLAIN_CTX, _attach_explain_and_kpis

    monkeypatch.setenv("ALLOW_NET", "1")
    _CHAT_EXPLAIN_CTX.set({"cid": "t", "t0": time.time(), "is_question": True, "policy": {"web_ok": True}, "tools": [], "kpi_done": False})

    payload = {"reply": "Ein 404 in Flask kommt oft von einer falschen Route…", "meta": {"sources": []}, "memory_ids": []}
    out = _attach_explain_and_kpis(
        payload,
        route="/api/chat",
        intent="coding",
        policy=None,
        tools=None,
        source_expected=True,
        sources_count=0,
    )
    assert out.get("reply") == "Ein 404 in Flask kommt oft von einer falschen Route…"
