def test_news_ranking_uses_prefs():
    from netapi.core.web_enricher import WebEnricher

    enricher = WebEnricher(enable_snapshots=False)

    results = [
        {"title": "Krone story", "url": "https://www.krone.at/1234567/story", "snippet": "x"},
        {"title": "ORF homepage", "url": "https://orf.at/", "snippet": "x"},
        {"title": "Standard article", "url": "https://www.derstandard.at/story/2000140000000/foo", "snippet": "x"},
        {"title": "APA", "url": "https://apa.at/news/abcdef", "snippet": "x"},
    ]

    prefs = {"preferred_sources": ["orf.at", "derstandard.at"], "blocked_sources": ["krone.at"]}

    ranked = enricher._apply_source_prefs_ranking(results, source_prefs=prefs, mode="news")

    assert [r.get("url") for r in ranked] == [
        "https://www.derstandard.at/story/2000140000000/foo",
        "https://orf.at/",
        "https://apa.at/news/abcdef",
        "https://www.krone.at/1234567/story",
    ]

    # Ensure blocked is still present, just downranked
    assert any("krone.at" in (r.get("url") or "") for r in ranked)
