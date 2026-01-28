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


def test_pdf_ingest_chat_once_includes_pdf_sources_and_trace(monkeypatch):
    monkeypatch.setenv("ALLOW_NET", "1")

    from netapi.app import app
    from starlette.testclient import TestClient
    from netapi.deps import get_current_user_opt, get_current_user_required
    from netapi.db import SessionLocal
    from netapi.models import User

    # Patch PDF fetcher to be deterministic/no network.
    from netapi.modules.tools import doc_fetch

    def _fake_fetch_pdf_text(url: str, *, timeout_s=15, max_bytes=0, max_pages=8):
        text = "[page 1] Hello PDF world.\n[page 2] Second page."
        sources = [{"title": "PDF", "url": url, "kind": "pdf", "origin": "pdf"}]
        meta = {"ok": True, "pages_read": 2, "pages_total": 10, "extractor": "pypdf"}
        return text, sources, meta

    monkeypatch.setattr(doc_fetch, "fetch_pdf_text", _fake_fetch_pdf_text)

    # Patch reasoner to be deterministic.
    from netapi.modules.chat import router as chat_router

    async def _fake_reason_about(*args, **kwargs):
        return {"text": "Antwort aus PDF: Hello PDF world. [page 1]"}

    monkeypatch.setattr(chat_router, "reason_about", _fake_reason_about)

    client = TestClient(app)

    paid_user = {"id": 7001, "role": "user", "roles": ["user"], "plan": "pro", "country_code": "AT"}

    def _paid():
        return paid_user

    app.dependency_overrides[get_current_user_opt] = _paid
    app.dependency_overrides[get_current_user_required] = _paid

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == int(paid_user["id"])).first()
        if not u:
            u = User(id=int(paid_user["id"]), username="test_pdf_paid", email="test_pdf_paid@example.com", plan="pro")
            db.add(u)
        else:
            u.plan = "pro"
        db.commit()
    finally:
        try:
            db.close()
        except Exception:
            pass

    msg = "Bitte lies https://example.com/a.pdf und sag mir, was drinsteht."
    r = client.post("/api/chat", json={"message": msg, "persona": "friendly", "lang": "de-DE", "conv_id": None, "web_ok": False})
    assert r.status_code == 200
    payload = r.json()

    assert payload.get("conv_id")
    assert payload.get("msg_id")
    assert isinstance(payload.get("meta"), dict)
    sources = payload["meta"].get("sources")
    assert isinstance(sources, list)
    assert any(isinstance(s, dict) and s.get("origin") == "pdf" for s in sources)
    assert any(isinstance(s, dict) and (s.get("page_hint") or s.get("pages_read")) for s in sources)

    tr = client.get("/api/chat/trace", params={"conv_id": int(payload["conv_id"]), "last": 1, "include_memory_preview": False})
    assert tr.status_code == 200
    j = tr.json()
    assert j.get("ok") is True
    assert isinstance(j.get("trace"), dict)
    assert any(isinstance(s, dict) and s.get("origin") == "pdf" for s in (j["trace"].get("sources") or []))


def test_pdf_ingest_stream_finalize_includes_pdf_sources_and_trace(monkeypatch):
    monkeypatch.setenv("ALLOW_NET", "1")
    monkeypatch.setenv("TEST_MODE", "1")

    from netapi.app import app
    from starlette.testclient import TestClient
    from netapi.deps import get_current_user_opt, get_current_user_required
    from netapi.db import SessionLocal
    from netapi.models import User

    from netapi.modules.tools import doc_fetch

    def _fake_fetch_pdf_text(url: str, *, timeout_s=15, max_bytes=0, max_pages=8):
        text = "[page 1] Hello PDF world."
        sources = [{"title": "PDF", "url": url, "kind": "pdf", "origin": "pdf"}]
        meta = {"ok": True, "pages_read": 1, "pages_total": 3, "extractor": "pypdf"}
        return text, sources, meta

    monkeypatch.setattr(doc_fetch, "fetch_pdf_text", _fake_fetch_pdf_text)

    from netapi.modules.chat import router as chat_router

    async def _fake_reason_about(*args, **kwargs):
        return {"text": "PDF Antwort: Hello PDF world. [page 1]"}

    monkeypatch.setattr(chat_router, "reason_about", _fake_reason_about)

    client = TestClient(app)

    paid_user = {"id": 7002, "role": "user", "roles": ["user"], "plan": "pro", "country_code": "AT"}

    def _paid():
        return paid_user

    app.dependency_overrides[get_current_user_opt] = _paid
    app.dependency_overrides[get_current_user_required] = _paid

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == int(paid_user["id"])).first()
        if not u:
            u = User(id=int(paid_user["id"]), username="test_pdf_stream", email="test_pdf_stream@example.com", plan="pro")
            db.add(u)
        else:
            u.plan = "pro"
        db.commit()
    finally:
        try:
            db.close()
        except Exception:
            pass

    msg = "Bitte lies https://example.com/a.pdf und fasse kurz zusammen."

    with client.stream(
        "GET",
        "/api/chat/stream",
        params={
            "message": msg,
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

    sources = final.get("sources")
    assert isinstance(sources, list)
    assert any(isinstance(s, dict) and s.get("origin") == "pdf" for s in sources)

    tr = client.get("/api/chat/trace", params={"conv_id": int(conv_id), "msg_id": int(msg_id), "include_memory_preview": False})
    assert tr.status_code == 200
    j = tr.json()
    assert j.get("ok") is True
    assert any(isinstance(s, dict) and s.get("origin") == "pdf" for s in (j.get("trace") or {}).get("sources") or [])
