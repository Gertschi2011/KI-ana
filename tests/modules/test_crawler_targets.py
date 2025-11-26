from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from netapi.app import app
from netapi.modules.crawler import api_router as api_router_module
from netapi.modules.crawler import targets as targets_module


@pytest.fixture(autouse=True)
def override_targets_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    dummy_path = tmp_path / "crawler_targets.json"
    monkeypatch.setattr(targets_module, "TARGETS_PATH", dummy_path, raising=False)
    monkeypatch.setattr(targets_module, "_LEGACY_SOURCES_PATH", tmp_path / "legacy.json", raising=False)
    monkeypatch.setattr(targets_module, "_TARGETS_LOCK", targets_module.threading.RLock(), raising=False)
    monkeypatch.setattr(api_router_module, "_STATUS_PATH", tmp_path / "crawler_state.json", raising=False)
    monkeypatch.setattr(api_router_module, "_KI_ROOT", tmp_path, raising=False)
    monkeypatch.setattr(api_router_module, "_CRAWLER_LOCK_PATH", tmp_path / "crawler.lock", raising=False)
    api_router_module._state.update({"running": False, "last_run_ts": 0, "last_error": None})
    if dummy_path.exists():
        dummy_path.unlink()
    yield
    if dummy_path.exists():
        dummy_path.unlink()


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[api_router_module._require_admin] = lambda: {
        "id": 1,
        "username": "test",
        "is_admin": True,
    }
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.pop(api_router_module._require_admin, None)
        client.close()


def load_targets_file(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_create_and_list_targets(client: TestClient, tmp_path: Path):
    initial = client.get("/api/crawler/targets").json()
    base_count = initial["count"]

    resp = client.post(
        "/api/crawler/targets",
        json={
            "label": "Docs",
            "url": "https://example.com/docs",
            "enabled": True,
            "interval_sec": 900,
            "tags": ["docs"],
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["item"]["label"] == "Docs"

    list_resp = client.get("/api/crawler/targets")
    assert list_resp.status_code == 200
    listed = list_resp.json()
    assert listed["count"] == base_count + 1
    assert any(entry["label"] == "Docs" for entry in listed["items"])


def test_update_target(client: TestClient):
    create = client.post(
        "/api/crawler/targets",
        json={
            "label": "Docs",
            "url": "https://example.com/docs",
            "enabled": True,
            "interval_sec": 900,
        },
    ).json()
    target_id = create["item"]["id"]

    update = client.put(
        f"/api/crawler/targets/{target_id}",
        json={
            "label": "Docs A",
            "interval_sec": 600,
            "tags": ["docs", "news"],
        },
    )
    assert update.status_code == 200
    data = update.json()
    assert data["item"]["label"] == "Docs A"
    assert data["item"]["interval_sec"] == 600
    assert set(data["item"]["tags"]) == {"docs", "news"}


def test_delete_target(client: TestClient):
    initial = client.get("/api/crawler/targets").json()
    base_count = initial["count"]
    create = client.post(
        "/api/crawler/targets",
        json={
            "label": "Docs",
            "url": "https://example.com/docs",
            "enabled": True,
            "interval_sec": 900,
        },
    ).json()
    target_id = create["item"]["id"]

    resp = client.delete(f"/api/crawler/targets/{target_id}")
    assert resp.status_code == 204

    list_resp = client.get("/api/crawler/targets")
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] == base_count


def test_update_unknown_target_returns_404(client: TestClient):
    resp = client.put(
        "/api/crawler/targets/does-not-exist",
        json={"label": "Nope"},
    )
    assert resp.status_code == 404
    payload = resp.json()
    assert payload["detail"]["error"] == "target_not_found"


def test_default_targets_seeded(tmp_path: Path):
    targets_module.ensure_targets_file()
    assert targets_module.TARGETS_PATH.exists()
    data = load_targets_file(targets_module.TARGETS_PATH)
    ids = {item["id"] for item in data}
    assert "internal-help" in ids
    assert "cybercrime-bmi" in ids
    assert "news-bbc-world" in ids


def test_create_target_from_url_endpoint(client: TestClient):
    resp = client.post(
        "/api/crawler/targets/from-url",
        json={
            "url": "https://www.bmi.gv.at/sicherundfairnetzt/cybercrime/aktuell.html",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["ok"] is True
    item = data["item"]
    assert "cybercrime" in item["tags"]
    assert item.get("trust") == pytest.approx(0.85)
    assert item.get("interval_sec") == 21600


def test_create_target_from_url_no_persist(client: TestClient):
    resp = client.post(
        "/api/crawler/targets/from-url",
        json={
            "url": "https://www.aljazeera.com/tag/cybercrime/",
            "persist": False,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["persisted"] is False

    listed = client.get("/api/crawler/targets").json()
    assert all(entry["url"] != "https://www.aljazeera.com/tag/cybercrime/" for entry in listed["items"])


def test_create_target_from_url_duplicate(client: TestClient):
    url = "https://www.dw.com/en/top-stories/europe/s-1432"
    first = client.post("/api/crawler/targets/from-url", json={"url": url})
    assert first.status_code == 201
    second = client.post("/api/crawler/targets/from-url", json={"url": url})
    assert second.status_code == 409
