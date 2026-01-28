import os


def test_extract_urls_and_pdf_detection():
    from netapi.modules.tools.doc_fetch import extract_urls, is_pdf_url

    txt = "Bitte lies https://example.com/a.pdf und auch https://example.com/b"
    urls = extract_urls(txt)
    assert "https://example.com/a.pdf" in urls
    assert "https://example.com/b" in urls
    assert is_pdf_url("https://example.com/a.pdf") is True
    assert is_pdf_url("https://example.com/b") is False


def test_fetch_pdf_text_net_disabled(monkeypatch):
    # Deterministic: should not attempt any network
    monkeypatch.setenv("ALLOW_NET", "0")
    from netapi.modules.tools.doc_fetch import fetch_pdf_text

    text, sources, meta = fetch_pdf_text("https://example.com/a.pdf")
    assert text is None
    assert sources == []
    assert meta.get("ok") is False

    # Restore env (pytest monkeypatch will revert automatically)
