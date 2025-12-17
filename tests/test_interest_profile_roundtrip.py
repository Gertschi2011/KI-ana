import json
from pathlib import Path


def test_interest_profile_roundtrip():
    from netapi.app import app
    from starlette.testclient import TestClient
    from netapi.deps import get_current_user_opt
    from netapi.core import addressbook
    from netapi import memory_store

    client = TestClient(app)

    app.dependency_overrides[get_current_user_opt] = lambda: {"id": 1, "role": "admin", "country_code": "AT"}

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
        "type": "interest_profile",
        "user_id": 1,
        "country": "AT",
        "lang": "de",
        "mode": "news",
        "category_weights": {"politik": 0.1},
        "domain_affinity": {"orf.at": 0.08},
    }

    r = client.post("/api/memory/store", json=payload)
    assert r.status_code == 200
    out = r.json()
    assert out.get("ok") is True
    assert out.get("type") == "interest_profile"
    bid = out.get("id")
    assert isinstance(bid, str) and bid

    indexed = addressbook.get_interest_profile(user_id=1, country="AT", lang="de", mode="news")
    assert indexed == bid

    r2 = client.post(
        "/api/memory/search",
        json={"type": "interest_profile", "user_id": 1, "country": "AT", "lang": "de", "mode": "news"},
    )
    assert r2.status_code == 200
    out2 = r2.json()
    assert out2.get("ok") is True
    assert out2.get("type") == "interest_profile"
    assert out2.get("block_id") == bid
    block = out2.get("block")
    assert isinstance(block, dict)
    meta = block.get("meta") or {}
    assert (meta.get("domain_affinity") or {}).get("orf.at") is not None

    try:
        p = memory_store.MEM_DIR / f"{bid}.json"
        if p.exists():
            p.unlink()
    except Exception:
        pass
