import json
from pathlib import Path


def test_chat_asks_for_sources_when_missing():
    from netapi.app import app
    from starlette.testclient import TestClient
    from netapi.deps import get_current_user_opt

    client = TestClient(app)

    # Override auth dependency so we have a stable user_id
    app.dependency_overrides[get_current_user_opt] = lambda: {"id": 1, "role": "admin", "country_code": "AT"}

    # Ensure no prefs exist for this user/locale
    data_path = Path(__file__).resolve().parents[1] / "memory" / "index" / "addressbook.json"
    if data_path.exists():
        raw = json.loads(data_path.read_text(encoding="utf-8") or "{}")
        prefs = raw.get("source_prefs") if isinstance(raw.get("source_prefs"), dict) else {}
        key = "prefs:sources:1:AT:de:news"
        if key in prefs:
            prefs.pop(key, None)
            raw["source_prefs"] = prefs
            data_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    r = client.post(
        "/api/v2/chat",
        json={"message": "Was sind die neuesten Nachrichten heute in Österreich?", "persona": "helpful", "lang": "de", "conv_id": None},
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload.get("ok") is True
    reply = payload.get("reply") or ""
    assert "Welche 1-3 Seiten bevorzugst du" in reply
    assert "Nachrichten" in reply
    meta = payload.get("meta") or {}
    assert meta.get("needs_source_prefs") is True
