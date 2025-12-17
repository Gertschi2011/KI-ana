import json
from pathlib import Path


def test_chat_signal_updates_interest_profile():
    from netapi.app import app
    from starlette.testclient import TestClient
    from netapi.deps import get_current_user_opt
    from netapi import memory_store

    client = TestClient(app)

    app.dependency_overrides[get_current_user_opt] = lambda: {"id": 1, "role": "admin", "country_code": "AT"}

    # Ensure clean index entry to avoid test pollution.
    data_path = Path(__file__).resolve().parents[1] / "memory" / "index" / "addressbook.json"
    if data_path.exists():
        raw = json.loads(data_path.read_text(encoding="utf-8") or "{}")
        idx = raw.get("interest_profiles") if isinstance(raw.get("interest_profiles"), dict) else {}
        key = "interest_profile:1:AT:de:news"
        if key in idx:
            idx.pop(key, None)
            raw["interest_profiles"] = idx
            data_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = {
        "user_id": 1,
        "country": "AT",
        "lang": "de",
        "mode": "news",
        "signal_type": "open_source",
        "domain": "example.com",
        "url": "https://example.com/article",
    }

    r = client.post("/api/v2/chat/signal", json=payload)
    assert r.status_code == 200
    out = r.json()
    assert out.get("ok") is True
    assert out.get("type") == "interest_profile"
    profile = out.get("profile")
    assert isinstance(profile, dict)
    assert (profile.get("domain_affinity") or {}).get("example.com") is not None

    bid = out.get("id")
    assert isinstance(bid, str) and bid

    try:
        p = memory_store.MEM_DIR / f"{bid}.json"
        if p.exists():
            p.unlink()
    except Exception:
        pass
