from __future__ import annotations

import io
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 KI_ana/1.0 +https://ki-ana.at/"
    )
}
DEFAULT_TIMEOUT = 15
DEFAULT_MAX_BYTES = 8 * 1024 * 1024


def _allow_net() -> bool:
    return str(os.getenv("ALLOW_NET", "1")).strip() == "1"


def is_pdf_url(url: str) -> bool:
    u = (url or "").strip().lower()
    if not u.startswith("http"):
        return False
    if ".pdf" in u:
        return True
    return False


def extract_urls(text: str) -> List[str]:
    if not text:
        return []
    # keep it simple; chat router already normalizes a lot
    urls = re.findall(r"https?://[^\s)\]]+", text)
    out: List[str] = []
    for u in urls:
        u = u.rstrip(". ,;\n\r\t")
        if u.startswith("http"):
            out.append(u)
    return out


def _download(url: str, *, timeout_s: int, max_bytes: int) -> Optional[bytes]:
    if not _allow_net():
        return None
    try:
        with requests.get(url, headers=HEADERS, timeout=timeout_s, stream=True) as r:
            r.raise_for_status()
            buf = io.BytesIO()
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                buf.write(chunk)
                if buf.tell() > int(max_bytes):
                    return None
            return buf.getvalue()
    except Exception:
        return None


def _extract_pdf_text_pypdf(pdf_bytes: bytes, *, max_pages: int = 8) -> Tuple[str, Dict[str, Any]]:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = reader.pages
        extracted: List[str] = []
        used_pages = 0
        for i, page in enumerate(pages[: int(max_pages)]):
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                extracted.append(f"[page {i + 1}] {txt}")
            used_pages += 1
        meta = {"extractor": "pypdf", "pages_read": used_pages, "pages_total": len(pages)}
        return "\n".join(extracted).strip(), meta
    except Exception as e:
        return "", {"extractor": "pypdf", "error": str(e)}


def fetch_pdf_text(
    url: str,
    *,
    timeout_s: int = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_pages: int = 8,
) -> Tuple[Optional[str], List[Dict[str, Any]], Dict[str, Any]]:
    """Fetch a PDF URL and return (text, sources, meta).

    sources entries are stable dicts: {title,url,kind:"pdf",origin:"pdf"}.
    """
    u = (url or "").strip()
    if not is_pdf_url(u) or not _allow_net():
        return None, [], {"ok": False, "reason": "not_pdf_or_net_disabled"}

    data = _download(u, timeout_s=int(timeout_s), max_bytes=int(max_bytes))
    if not data:
        return None, [{"title": "PDF", "url": u, "kind": "pdf", "origin": "pdf"}], {"ok": False, "reason": "download_failed_or_too_large"}

    text, meta = _extract_pdf_text_pypdf(data, max_pages=int(max_pages))
    sources = [{"title": "PDF", "url": u, "kind": "pdf", "origin": "pdf"}]
    if not text:
        meta = {**meta, "ok": False, "reason": "extract_failed_or_empty"}
        return None, sources, meta

    meta = {**meta, "ok": True}
    return text, sources, meta
