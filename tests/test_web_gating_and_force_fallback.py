import requests


def test_try_web_answer_short_query_no_net(monkeypatch):
    # If gating works, we must not attempt any HTTP at all.
    called = {"n": 0}

    def boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("network call should not happen")

    monkeypatch.setattr(requests, "get", boom)

    from netapi.modules.chat import router as chat_router

    text, sources = chat_router.try_web_answer("mars", limit=3)
    assert text is None
    assert sources == []
    assert called["n"] == 0


def test_force_web_answer_no_wikipedia_fallback(monkeypatch):
    # Previously this hit Wikipedia; now it must behave like try_web_answer (gated).
    called = {"n": 0}

    def boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("network call should not happen")

    monkeypatch.setattr(requests, "get", boom)

    from netapi.modules.chat import router as chat_router

    text, sources = chat_router._force_web_answer("albert einstein", limit=3)
    assert text is None
    assert sources == []
    assert called["n"] == 0


def test_try_web_answer_research_uses_web_fetch(monkeypatch):
    # Stub the web_fetch implementation so this test is deterministic.
    from netapi.modules.tools import web_fetch

    def fake_fetch(q: str, *, lang: str = "de", max_results: int = 3, max_chars: int = 900):
        return (
            "Kurzüberblick: Beispielantwort.",
            [
                {
                    "title": "Example",
                    "url": "https://example.com/report",
                    "kind": "web",
                    "origin": "web",
                }
            ],
        )

    monkeypatch.setattr(web_fetch, "web_search_and_summarize", fake_fetch)

    from netapi.modules.chat import router as chat_router

    q = "Laut Statistik 2024: Arbeitslosenquote Österreich"
    text, sources = chat_router.try_web_answer(q, limit=3)

    assert text
    assert "Beispielantwort" in text
    assert sources and sources[0].get("url") == "https://example.com/report"
