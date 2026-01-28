import json
from typing import Optional, Dict, Any

import pytest
import httpx
from fastapi.testclient import TestClient

from netapi.app import app


def test_intent_guard_chat_once_returns_clarifying_questions_and_empty_sources():
    client = TestClient(app)
    r = client.post("/api/chat", json={"message": "Bitte \u00fcbersetze das"})
    assert r.status_code in (200, 401)
    if r.status_code == 401:
        pytest.skip("Auth required for /api/chat in this environment")
    data = r.json()
    assert data.get("ok") is True
    assert isinstance(data.get("reply"), str)
    assert "Kontext" in data.get("reply") or "Text" in data.get("reply")

    # Transparency contract: always present and empty
    assert isinstance(data.get("sources"), list)
    assert data.get("sources") == []
    assert isinstance(data.get("memory_ids"), list)
    assert data.get("memory_ids") == []

    ex = data.get("explain")
    assert isinstance(ex, dict)
    note = str(ex.get("note") or "")
    assert "Noch kein Kontext" in note


@pytest.mark.asyncio
async def test_intent_guard_sse_finalize_has_empty_sources_and_note():
    def _parse_sse_event(line: str) -> Optional[Dict[str, Any]]:
        line = (line or "").strip()
        if not line:
            return None
        if line.startswith("data:"):
            data_part = line[5:].strip()
            if not data_part:
                return None
            try:
                return json.loads(data_part)
            except Exception:
                return None
        return None

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=30.0) as client:
        params = {"message": "Fass zusammen", "web_ok": "0"}
        headers = {"Accept": "text/event-stream"}

        async with client.stream("GET", "/api/chat/stream", params=params, headers=headers) as resp:
            assert resp.status_code in (200, 401)
            if resp.status_code == 401:
                pytest.skip("Auth required for /api/chat/stream in this environment")

            final_payload: Optional[Dict[str, Any]] = None
            async for line in resp.aiter_lines():
                evt = _parse_sse_event(line)
                if not evt:
                    continue
                if evt.get("done") is True or evt.get("type") == "finalize":
                    final_payload = evt
                    break

            assert final_payload is not None
            assert final_payload.get("done") is True
            assert isinstance(final_payload.get("text"), str)
            assert isinstance(final_payload.get("sources"), list)
            assert final_payload.get("sources") == []
            assert isinstance(final_payload.get("memory_ids"), list)
            assert final_payload.get("memory_ids") == []
            ex = final_payload.get("explain")
            assert isinstance(ex, dict)
            note = str(ex.get("note") or "")
            assert "Noch kein Kontext" in note
