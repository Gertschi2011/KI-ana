import os
import sys
import sqlite3
import time
import json
import pytest

# Ensure env points to project DB
DB_PATH = os.path.expanduser(os.getenv("DATABASE_URL", "sqlite:////home/kiana/ki_ana/db.sqlite3").replace("sqlite:///", "").replace("sqlite://", ""))


def wait_for_db_row(source_like: str, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, source, tags FROM knowledge_blocks WHERE source LIKE ? ORDER BY id DESC LIMIT 1", (source_like,))
            row = cur.fetchone()
            if row:
                return row
        time.sleep(0.05)
    return None


def test_save_memory_entry_creates_row():
    from netapi import memory_store
    title = "Mars"
    content = "Der Mars ist der vierte Planet von der Sonne. Er ist ein Gesteinsplanet."
    tags = ["vision", "learned", "web"]
    res = memory_store.save_memory_entry(title=title, content=content, tags=tags, url="https://example.org/mars")
    assert isinstance(res, dict)
    assert "id" in res
    row = wait_for_db_row("Mars")
    assert row is not None
    rid, source, tagcsv = row
    assert source == "Mars"
    assert "vision" in (tagcsv or "")


def test_viewer_endpoints_list_and_export():
    from netapi.app import app
    from starlette.testclient import TestClient
    client = TestClient(app)
    # List
    r = client.get("/api/memory/knowledge/list", params={"q": "Mars", "page": 1, "limit": 10, "sort": "desc"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    items = data.get("items") or []
    assert isinstance(items, list)
    # CSV export (public)
    r2 = client.get("/api/memory/knowledge/export.csv", params={"q": "Mars"})
    assert r2.status_code == 200
    assert "text/csv" in (r2.headers.get("content-type") or "")
    # JSON export (secured): only attempt if ADMIN_API_TOKEN present
    admin_tok = os.getenv("ADMIN_API_TOKEN", "").strip()
    if admin_tok:
        r3 = client.get("/api/memory/knowledge/export.json", params={"q": "Mars"}, headers={"Authorization": f"Bearer {admin_tok}"})
        assert r3.status_code == 200
        assert "application/json" in (r3.headers.get("content-type") or "")


def test_viewer_item_modal():
    from netapi.app import app
    from starlette.testclient import TestClient
    client = TestClient(app)
    # Get first item id (if exists)
    r = client.get("/api/memory/knowledge/list", params={"page":1, "limit":1})
    assert r.status_code == 200
    data = r.json(); items = data.get("items") or []
    if not items:
        pytest.skip("no items available for modal test")
    rid = items[0].get("row_id")
    assert isinstance(rid, int)
    r2 = client.get(f"/api/memory/knowledge/item/{rid}")
    assert r2.status_code == 200
    j = r2.json()
    assert j.get("ok") is True
    assert isinstance(j.get("item"), dict)


def test_viewer_minio_export(monkeypatch):
    from netapi.app import app
    from starlette.testclient import TestClient
    client = TestClient(app)
    admin_tok = os.getenv("ADMIN_API_TOKEN", "").strip()
    if not admin_tok:
        pytest.skip("ADMIN_API_TOKEN not set; skipping secured minio export test")
    # Fake boto3 client
    calls = {}
    class FakeS3:
        def put_object(self, Bucket, Key, Body, ContentType):
            calls["Bucket"] = Bucket; calls["Key"] = Key; calls["CT"] = ContentType; calls["BodyLen"] = len(Body or b"")
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}
    class FakeBoto3:
        def client(self, *_args, **_kwargs):
            return FakeS3()
    # Patch boto3 globally so any `import boto3` resolves to our fake
    monkeypatch.setenv("MINIO_BUCKET", "test-bucket")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://localhost:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "x")
    monkeypatch.setenv("MINIO_SECRET_KEY", "y")
    monkeypatch.setenv("MINIO_USE_SSL", "0")
    monkeypatch.setitem(sys.modules, "boto3", FakeBoto3())
    r = client.get("/api/memory/knowledge/export.minio", params={"q": "Mars"}, headers={"Authorization": f"Bearer {admin_tok}"})
    assert r.status_code == 200
    js = r.json(); assert js.get("status") == "ok"
    assert calls.get("Bucket") == "test-bucket"
    assert isinstance(calls.get("Key"), str) and calls["Key"].startswith("knowledge/")
    assert calls.get("BodyLen", 0) > 0


@pytest.mark.timeout(5)
def test_chat_stream_no_ask_save_flag():
    from netapi.app import app
    from starlette.testclient import TestClient
    client = TestClient(app)
    with client.stream("GET", "/api/chat/stream", params={"message": "Mars", "lang": "de-DE", "web_ok": 1, "autonomy": 1}) as resp:
        assert resp.status_code == 200
        ct = resp.headers.get("content-type") or ""
        assert "text/event-stream" in ct or "event-stream" in ct
        buf = ""
        for i, line in enumerate(resp.iter_lines()):
            if not line:
                continue
            try:
                if isinstance(line, (bytes, bytearray)):
                    line = line.decode("utf-8", errors="ignore")
                if line.startswith("data:"):
                    payload = line[len("data:"):].strip()
                    buf += payload + "\n"
                    # Stop after some chunks to avoid long test
                    if i > 8:
                        break
            except Exception:
                break
        # Ensure ask_save is not present in any meta
        assert "ask_save" not in buf
