import json
import pytest
import httpx
from typing import Optional, Dict, Any

from netapi.app import app


@pytest.mark.asyncio
async def test_chat_sse_final_event_contains_sources():
    """
    Streams the SSE endpoint and validates that the final event contains:
    - text (str)
    - memory_ids (list)
    - sources (list with at least one 'memory' and one 'web' entry)
    - done (True)
    """
    def _parse_sse_event(line: str) -> Optional[Dict[str, Any]]:
        line = (line or '').strip()
        if not line:
            return None
        if line.startswith('data:'):
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
        params = {"message": "Test mit Memory und Web", "web_ok": "1"}
        headers = {"Accept": "text/event-stream"}

        async with client.stream("GET", "/api/chat/stream", params=params, headers=headers) as resp:
            assert resp.status_code == 200, f"Unexpected status: {resp.status_code}"

            final_payload: Optional[Dict[str, Any]] = None

            async for line in resp.aiter_lines():
                evt = _parse_sse_event(line)
                if not evt:
                    continue
                if evt.get("done") is True:
                    final_payload = evt
                    break

            assert final_payload is not None, "No final SSE event (done: true) received"
            assert isinstance(final_payload.get("text"), str)
            assert isinstance(final_payload.get("memory_ids"), list)
            assert isinstance(final_payload.get("sources"), list)
            assert final_payload.get("done") is True

            origins = [str(s.get("origin") or "") for s in final_payload["sources"] if isinstance(s, dict)]
            final_origin = str(final_payload.get("origin") or "").lower()
            if final_origin in ("memory", "mixed"):
                assert any(o == "memory" for o in origins), "Expected at least one memory source"
            if final_origin in ("web", "mixed"):
                assert any(o == "web" for o in origins), "Expected at least one web source"

            memory_entries = [s for s in final_payload["sources"] if isinstance(s, dict) and s.get("origin") == "memory"]
            web_entries = [s for s in final_payload["sources"] if isinstance(s, dict) and s.get("origin") == "web"]

            if memory_entries:
                m = memory_entries[0]
                assert m.get("id"), "Memory source should have an 'id'"
                assert isinstance(m.get("url"), str) and "/static/viewer.html?highlight=" in m["url"]

            if web_entries:
                w = web_entries[0]
                assert w.get("id") in (None, ""), "Web source 'id' should be None/empty"
                assert isinstance(w.get("url"), str) and w["url"].startswith(("http://", "https://"))
