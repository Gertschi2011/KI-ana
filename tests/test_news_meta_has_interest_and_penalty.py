def test_meta_web_includes_interest_and_service_penalty_fields():
    from netapi.modules.chat.clean_router import _build_meta_web

    raw = {
        "used": True,
        "provider": "serper",
        "mode": "news",
        "country": "AT",
        "lang": "de",
        "generated_at": "2025-01-01T00:00:00Z",
        "relevance_applied": True,
        "dedup_applied": True,
        "service_penalty_applied": True,
        "penalized_examples": [{"title": "Foo", "domain": "parlament.gv.at", "reason": "gov_pr"}],
        "interest_used": True,
        "top_categories": ["politik"],
        "top_domains": ["orf.at"],
        "news_cards": [
            {"title": "A", "url": "https://orf.at/a", "domain": "orf.at", "source": "ORF", "date": "vor 2 Stunden"}
        ],
    }

    meta = _build_meta_web(raw, {"country_code": "AT", "lang": "de"}, force_mode="news")
    assert meta.get("used") is True
    assert meta.get("service_penalty_applied") is True
    assert isinstance(meta.get("penalized_examples"), list)
    assert meta.get("interest_used") is True
