def _mk(title: str, url: str, snippet: str = "", published: str = ""):
    return {"title": title, "url": url, "snippet": snippet, "published": published}


def test_service_penalty_reorder_only_and_examples():
    from netapi.core.news_relevance import apply_relevance_reorder, apply_service_penalty_reorder

    results = [
        _mk("News: Regierung beschließt Paket", "https://derstandard.at/a", "politik", "vor 3 Stunden"),
        _mk("Amtsblatt: Veröffentlichung", "https://parlament.gv.at/PAKT/", "amtsblatt", "vor 2 Tagen"),
        _mk("Newsletter: Audio jetzt verfügbar", "https://example.com/newsletter", "newsletter", "vor 5 Tagen"),
        _mk("News: Inflation sinkt", "https://orf.at/b", "wirtschaft", "vor 4 Stunden"),
    ]

    ranked, _meta = apply_relevance_reorder(results, query="Österreich Nachrichten", top_n_considered=10)
    out, svc_meta = apply_service_penalty_reorder(ranked, query="Österreich Nachrichten", top_n_considered=10)

    assert svc_meta.applied is True
    assert len(out) == len(results)
    assert {r["url"] for r in out} == {r["url"] for r in results}

    # Expect at least one penalized example (gov/service/stale).
    assert isinstance(svc_meta.penalized_examples, list)
    assert len(svc_meta.penalized_examples) >= 1
    assert all(isinstance(e, dict) for e in svc_meta.penalized_examples)
