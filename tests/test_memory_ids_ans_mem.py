import os
from fastapi.testclient import TestClient

from netapi.app import app


def _force_knowledge_path(monkeypatch, *, topic_path: str = "test/topic"):
    # Force the router into the knowledge intent so it reaches the ans_mem branch.
    import netapi.modules.chat.router as chat_router

    monkeypatch.setattr(chat_router, "detect_intent", lambda _msg: "knowledge")
    # Ensure no menu/choice shortcut can intercept this request.
    monkeypatch.setattr(chat_router, "pick_choice", lambda _msg: None)
    monkeypatch.setattr(chat_router, "get_last_offer", lambda _sid=None: None)
    # Avoid KM/addressbook intercepts so ans_mem is used.
    monkeypatch.setattr(chat_router, "km_find_relevant_blocks", lambda *a, **k: [])
    # Ensure topic_path is stable and non-empty when needed.
    monkeypatch.setattr(chat_router, "perceive", lambda _msg, _state=None: {"topic_path": topic_path})


def test_memory_ids_ans_mem_short_term_topic_hit(monkeypatch):
    os.environ.setdefault("TEST_MODE", "1")
    _force_knowledge_path(monkeypatch, topic_path="test/topic")

    # Patch memory_store functions used by ans_mem branch.
    import netapi.memory_store as memory_store

    monkeypatch.setattr(memory_store, "topic_index_list", lambda _topic_path: ["st_123"], raising=False)
    monkeypatch.setattr(
        memory_store,
        "load_short_term_block",
        lambda _block_id: {"id": "st_123", "info": "Short-term memory answer."},
        raising=False,
    )
    monkeypatch.setattr(memory_store, "increment_use", lambda *_a, **_k: None, raising=False)
    monkeypatch.setattr(memory_store, "maybe_promote", lambda *_a, **_k: None, raising=False)

    client = TestClient(app)
    r = client.post("/api/chat", json={"message": "Was weißt du über test?"})
    assert r.status_code == 200
    data = r.json()

    assert data.get("ok") is True
    assert isinstance(data.get("reply"), str) and data["reply"].strip()
    assert data.get("memory_ids") == ["st_123"]


def test_memory_ids_ans_mem_long_term_search_hit(monkeypatch):
    os.environ.setdefault("TEST_MODE", "1")
    _force_knowledge_path(monkeypatch, topic_path="")

    import netapi.memory_store as memory_store

    monkeypatch.setattr(memory_store, "topic_index_list", lambda _topic_path: [], raising=False)
    monkeypatch.setattr(memory_store, "search_blocks", lambda query, top_k=3, min_score=0.10: [("bid_9", 0.99)], raising=False)
    monkeypatch.setattr(memory_store, "get_block", lambda bid: {"id": bid, "content": "Long-term memory answer."}, raising=False)

    client = TestClient(app)
    r = client.post("/api/chat", json={"message": "Erklär mir bitte bid"})
    assert r.status_code == 200
    data = r.json()

    assert data.get("ok") is True
    assert isinstance(data.get("reply"), str) and data["reply"].strip()
    assert data.get("memory_ids") == ["bid_9"]
