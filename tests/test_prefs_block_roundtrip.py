import json
from pathlib import Path


def test_prefs_block_roundtrip():
    from netapi.app import app
    from starlette.testclient import TestClient
    from netapi.deps import get_current_user_opt
    from netapi.core import addressbook
    from netapi import memory_store

    client = TestClient(app)

    # Override auth dependency so /api/memory/* is callable in tests
    app.dependency_overrides[get_current_user_opt] = lambda: {"id": 1, "role": "admin", "country_code": "AT"}

    # Ensure clean slate for this user
    data_path = Path(__file__).resolve().parents[1] / "memory" / "index" / "addressbook.json"
    if data_path.exists():
        raw = json.loads(data_path.read_text(encoding="utf-8") or "{}")
        prefs = raw.get("source_prefs") if isinstance(raw.get("source_prefs"), dict) else {}
        key = "prefs:sources:1:AT:de:news"
        if key in prefs:
            prefs.pop(key, None)
            raw["source_prefs"] = prefs
            data_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = {
        "type": "user_source_prefs",
        "user_id": 1,
        "country": "AT",
        "lang": "de",
        "intent": "news",
        "preferred_sources": ["orf.at", "derstandard.at"],
        "blocked_sources": ["krone.at"],
    }

    r = client.post("/api/memory/store", json=payload)
    assert r.status_code == 200
    out = r.json()
    assert out.get("ok") is True
    assert out.get("type") == "user_source_prefs"
    bid = out.get("id")
    assert isinstance(bid, str) and bid

    # Verify index points to the stored block
    indexed = addressbook.get_source_prefs(user_id=1, country="AT", lang="de", intent="news")
    assert indexed == bid

    r2 = client.post(
        "/api/memory/search",
        json={"type": "user_source_prefs", "user_id": 1, "country": "AT", "lang": "de", "intent": "news"},
    )
    assert r2.status_code == 200
    out2 = r2.json()
    assert out2.get("ok") is True
    assert out2.get("block_id") == bid
    block = out2.get("block")
    assert isinstance(block, dict)
    meta = block.get("meta") or {}
    assert "derstandard.at" in (meta.get("preferred_sources") or [])
    assert "krone.at" in (meta.get("blocked_sources") or [])

    # Cleanup: remove block file to avoid bloating repo in repeated test runs
    try:
        p = memory_store.MEM_DIR / f"{bid}.json"
        if p.exists():
            p.unlink()
    except Exception:
        pass
