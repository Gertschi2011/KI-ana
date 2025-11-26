from __future__ import annotations
import os, json, hashlib, time, re, threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from html.parser import HTMLParser

KI_ROOT = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
CRAWLED_DIR = KI_ROOT / "memory" / "crawled"
BLOCKS_DIR = KI_ROOT / "memory" / "long_term" / "blocks"
TARGETS_FILE = KI_ROOT / "system" / "crawler_targets.json"
LEGACY_SOURCES_FILE = KI_ROOT / "system" / "crawl_sources.json"
INDEX_FILE = KI_ROOT / "memory" / "index" / "crawled_index.json"
TRUST_INDEX = KI_ROOT / "memory" / "index" / "trust_index.json"
GOALS_PATH = KI_ROOT / "memory" / "index" / "goals.json"

CRAWLED_DIR.mkdir(parents=True, exist_ok=True)
(BLOCKS_DIR).mkdir(parents=True, exist_ok=True)
(INDEX_FILE.parent).mkdir(parents=True, exist_ok=True)

try:  # Prefer shared config helpers when running inside the API package
    from netapi.modules.crawler.targets import (
        ensure_targets_file as _ensure_targets_file,
        load_targets as _shared_load_targets,
        save_targets as _shared_save_targets,
    )
except Exception:  # pragma: no cover - fallback for stand-alone runs
    _ensure_targets_file = None
    _shared_load_targets = None
    _shared_save_targets = None


_RUN_LOCK = threading.RLock()


def _truncate(message: str, limit: int = 200) -> str:
    msg = (message or "").strip()
    if len(msg) <= limit:
        return msg
    return msg[: limit - 1] + "…"


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._buf: List[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            d = (data or "").strip()
            if d:
                self._buf.append(d)

    def text(self) -> str:
        t = " ".join(self._buf)
        # normalize whitespace
        t = re.sub(r"\s+", " ", t)
        return t.strip()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


_FALLBACK_DEFAULT_TARGETS: List[Dict[str, Any]] = [
    {
        "id": "ki-ana-docs",
        "label": "KI_ana Dokumentation",
        "url": "https://ki-ana.at/static/docs/index.html",
        "enabled": True,
        "interval_sec": 1800,
        "last_run_ts": 0,
        "last_status": None,
        "tags": ["docs", "ki_ana"],
    }
]


def _fallback_normalize_target(item: Dict[str, Any]) -> Dict[str, Any]:
    target = dict(item)
    target["id"] = str(target.get("id") or f"target-{int(time.time())}")
    target["label"] = str(target.get("label") or target["id"]).strip() or target["id"]
    target["url"] = str(target.get("url") or "").strip()
    target["enabled"] = bool(target.get("enabled", True))
    try:
        target["interval_sec"] = max(60, int(target.get("interval_sec") or 1800))
    except Exception:
        target["interval_sec"] = 1800
    try:
        target["last_run_ts"] = int(target.get("last_run_ts") or 0)
    except Exception:
        target["last_run_ts"] = 0
    status = target.get("last_status")
    if status is not None and not isinstance(status, dict):
        target["last_status"] = {"message": str(status)}
    else:
        target["last_status"] = status
    tags = target.get("tags")
    if isinstance(tags, (list, tuple)):
        target["tags"] = [str(t).strip() for t in tags if str(t).strip()]
    else:
        target["tags"] = []
    return target


def _fallback_load_legacy_targets() -> List[Dict[str, Any]]:
    if not LEGACY_SOURCES_FILE.exists():
        return []
    try:
        data = json.loads(LEGACY_SOURCES_FILE.read_text(encoding="utf-8")) or []
    except Exception:
        return []
    targets: List[Dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("url") or "").strip()
        if not url:
            continue
        label = str(entry.get("title") or entry.get("label") or url).strip() or url
        interval_raw = entry.get("interval_sec")
        if interval_raw is None:
            minutes = entry.get("minutes")
            try:
                interval_raw = int(minutes) * 60
            except Exception:
                interval_raw = 1800
        try:
            interval_sec = max(60, int(interval_raw))
        except Exception:
            interval_sec = 1800
        normalized = _fallback_normalize_target(
            {
                "id": f"legacy-{hashlib.sha1(url.encode('utf-8')).hexdigest()[:8]}",
                "label": label,
                "url": url,
                "enabled": bool(entry.get("enabled", True)),
                "interval_sec": interval_sec,
                "last_run_ts": entry.get("last_run_ts"),
                "last_status": entry.get("last_status"),
                "tags": entry.get("tags") or [],
            }
        )
        try:
            normalized["trust"] = float(entry.get("trust", normalized.get("trust", 0.6) or 0.6))
        except Exception:
            normalized["trust"] = normalized.get("trust", 0.6) or 0.6
        targets.append(normalized)
    return targets or list(_FALLBACK_DEFAULT_TARGETS)


def _fallback_ensure_targets_file() -> None:
    TARGETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TARGETS_FILE.exists():
        return
    seeds = _fallback_load_legacy_targets()
    if not seeds:
        seeds = list(_FALLBACK_DEFAULT_TARGETS)
    TARGETS_FILE.write_text(json.dumps(seeds, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_targets() -> None:
    if _ensure_targets_file is not None:
        try:
            _ensure_targets_file()
            return
        except Exception:
            pass
    _fallback_ensure_targets_file()


def _load_targets() -> List[Dict[str, Any]]:
    _ensure_targets()
    if _shared_load_targets is not None:
        try:
            return _shared_load_targets()
        except Exception:
            pass
    try:
        data = json.loads(TARGETS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [_fallback_normalize_target(item) for item in data if isinstance(item, dict)]
    except Exception:
        pass
    return list(_FALLBACK_DEFAULT_TARGETS)


def _save_targets(targets: List[Dict[str, Any]]) -> None:
    if _shared_save_targets is not None:
        try:
            _shared_save_targets(targets)
            return
        except Exception:
            pass
    TARGETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TARGETS_FILE.write_text(
        json.dumps([_fallback_normalize_target(t) for t in targets], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def crawl_html(url: str, timeout: int = 15) -> Tuple[str, str, Optional[int], Optional[str]]:
    """Return (text, html, status_code, error_message)."""
    status_code: Optional[int] = None
    try:
        req = Request(url, headers={"User-Agent": "KI_anaCrawler/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            status_code = getattr(resp, "status", getattr(resp, "code", None))
            raw = resp.read().decode("utf-8", errors="ignore")
        parser = _TextExtractor()
        parser.feed(raw)
        return parser.text(), raw, status_code or 200, None
    except HTTPError as exc:  # pragma: no cover
        status_code = getattr(exc, "code", None) or 500
        return "", "", status_code, _truncate(str(exc))
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        return "", "", None, _truncate(str(reason))
    except TimeoutError as exc:  # pragma: no cover
        return "", "", None, _truncate(str(exc))
    except Exception as exc:
        return "", "", None, _truncate(str(exc))


def _save_crawled(doc: Dict[str, Any]) -> Path:
    h = doc.get("hash") or _sha256((doc.get("url") or "") + (doc.get("text") or ""))
    ts = int(time.time())
    path = CRAWLED_DIR / f"{ts}_{h}.json"
    try:
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return path


def _load_crawled_index() -> Dict[str, Dict[str, Any]]:
    if not INDEX_FILE.exists():
        return {}
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _save_crawled_index(idx: Dict[str, Dict[str, Any]]) -> None:
    try:
        INDEX_FILE.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def promote_crawled_to_blocks(min_trust: float = 0.5, max_promote: int = 50) -> int:
    """Promote trusted, novel crawled docs to long-term memory blocks."""
    promoted = 0
    idx = _load_crawled_index()
    for fname in sorted(CRAWLED_DIR.glob("*.json")):
        try:
            data = json.loads(fname.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if float(data.get("score", 0.0)) < float(min_trust):
            continue
        h = data.get("hash")
        if not h or (BLOCKS_DIR / f"{h}.json").exists():
            continue
        block = {
            "id": h,
            "title": data.get("title") or data.get("url") or "(ohne Titel)",
            "content": data.get("text") or "",
            "tags": ["web", "crawl"],
            "url": data.get("url"),
            "source": data.get("source") or "crawl",
            "created": int(time.time()),
        }
        try:
            try:
                from .. import memory_store as _mem  # type: ignore

                if hasattr(_mem, "add_block"):
                    _mem.add_block(
                        title=block["title"],
                        content=block["content"],
                        tags=block["tags"],
                        url=block["url"],
                        meta={"id": h, "source": block["source"]},
                    )
            except Exception:
                pass
            (BLOCKS_DIR / f"{h}.json").write_text(json.dumps(block, ensure_ascii=False, indent=2), encoding="utf-8")
            promoted += 1
        except Exception:
            continue
        if promoted >= max_promote:
            break
    return promoted


def _current_goal_tags() -> List[str]:
    try:
        if not GOALS_PATH.exists():
            return []
        goals = json.loads(GOALS_PATH.read_text(encoding="utf-8"))
        tags: List[str] = []
        if isinstance(goals, list):
            for g in goals:
                for t in (g.get("tags") or []):
                    tt = str(t).lower().strip()
                    if tt:
                        tags.append(tt)
        return sorted(list(set(tags)))
    except Exception:
        return []


def _score_doc(domain: str, text: str, trust_map: Dict[str, float]) -> float:
    base = trust_map.get(domain, trust_map.get("*", 0.5))
    bonus = 0.0
    if len(text) > 2000:
        bonus += 0.05
    if any(k in text.lower() for k in ["gesetz", "krieg", "gefahr", "wissenschaft", "forschung", "ethik"]):
        bonus += 0.05
    try:
        for tg in _current_goal_tags():
            if tg and tg in text.lower():
                bonus += 0.08
    except Exception:
        pass
    return max(0.0, min(1.0, base)) + min(0.2, bonus)


def run_crawler_once(force: bool = False) -> Dict[str, Any]:
    started_wall = int(time.time())
    started_monotonic = time.perf_counter()

    with _RUN_LOCK:
        targets = _load_targets()
        total_targets = len(targets)
        enabled_targets = [t for t in targets if t.get("enabled")]
        enabled_count = len(enabled_targets)

        def _finalize_response(payload: Dict[str, Any], selected_count: int = 0) -> Dict[str, Any]:
            finished_wall = int(time.time())
            duration_ms = max(0, int((time.perf_counter() - started_monotonic) * 1000))
            results_payload = payload.setdefault("results", [])
            payload.setdefault("errors", 0)
            payload.setdefault("fetched", 0)
            payload.setdefault("saved", 0)
            payload.setdefault("targets_processed", len(results_payload))
            payload.setdefault("targets_selected", selected_count if selected_count >= 0 else 0)
            payload.setdefault("skipped_targets", max(0, total_targets - payload["targets_selected"]))
            base = {
                "targets_total": total_targets,
                "targets_enabled": enabled_count,
                "started_at": started_wall,
                "finished_at": finished_wall,
                "duration_ms": duration_ms,
            }
            base.update(payload)
            return base

        if not targets:
            return _finalize_response(
                {
                    "ok": False,
                    "error": "no_targets",
                    "message": "Keine Crawler-Ziele konfiguriert",
                },
                selected_count=0,
            )

        if not enabled_targets:
            return _finalize_response(
                {
                    "ok": False,
                    "error": "no_enabled_targets",
                    "message": "Es sind keine aktiven Ziele vorhanden",
                },
                selected_count=0,
            )

        now_ts = int(time.time())

        def _interval_due(item: Dict[str, Any]) -> bool:
            try:
                interval = int(item.get("interval_sec") or 1800)
            except Exception:
                interval = 1800
            interval = max(60, min(interval, 24 * 3600))
            last_ts = int(item.get("last_run_ts") or 0)
            return (now_ts - last_ts) >= interval

        if force:
            selected_targets = enabled_targets
        else:
            selected_targets = [t for t in enabled_targets if _interval_due(t)]

        if not selected_targets and not force:
            payload = {"ok": True, "message": "no_targets_due", "skipped_targets": total_targets}
            return _finalize_response(payload, selected_count=0)

        idx = _load_crawled_index()
        stats = {"fetched": 0, "saved": 0}
        triggered_topics: List[str] = []
        results: List[Dict[str, Any]] = []

        for target in selected_targets:
            run_ts = int(time.time())
            target_id = str(target.get("id") or target.get("label") or target.get("url") or "target")
            url = str(target.get("url") or "").strip()
            label = str(target.get("label") or target_id).strip() or target_id
            domain = str(target.get("domain") or re.sub(r"^https?://([^/]+)/?.*", r"\1", url)).strip()
            try:
                trust_val = float(target.get("trust", 0.6) or 0.6)
            except Exception:
                trust_val = 0.6
            trust_val = max(0.0, min(trust_val, 1.0))
            target["trust"] = trust_val
            trust_map = {domain: trust_val, "*": trust_val}

            started_target = time.perf_counter()
            pages = 0
            new_items = 0
            status_code: Optional[int] = None
            error_details: List[str] = []
            message = ""
            ok = False

            if not url:
                error_details.append("missing_url")
                message = "missing_url"
            else:
                text, _, status_code, fetch_error = crawl_html(url)
                if fetch_error:
                    error_details.append(fetch_error)
                if text:
                    pages = 1
                    stats["fetched"] += 1
                    hash_id = _sha256(url + "\n" + text[:4096])
                    if hash_id in idx:
                        message = "unchanged"
                        ok = True
                    else:
                        score = _score_doc(domain, text, trust_map)
                        snippet_tags: List[str] = []
                        low = (label + "\n" + text[:400]).lower()
                        for key in ["gesetz", "krieg", "gefahr", "notstand", "krise", "warnung"]:
                            if key in low:
                                snippet_tags.append(key)
                        doc = {
                            "url": url,
                            "title": label,
                            "domain": domain,
                            "hash": hash_id,
                            "score": score,
                            "text": text[:200000],
                            "tags": snippet_tags,
                        }
                        path = _save_crawled(doc)
                        idx[hash_id] = {"file": str(path), "url": url, "score": score}
                        stats["saved"] += 1
                        new_items = 1
                        ok = True
                        message = "fetched"
                        if detect_critical_context(snippet_tags):
                            try:
                                from . import self_reflection as _sr  # type: ignore

                                res = _sr.reflect_context_change(tags=snippet_tags, source=url, title=label)  # type: ignore
                                if res.get("ok") and res.get("topic"):
                                    triggered_topics.append(str(res.get("topic")))
                            except Exception:
                                pass
                else:
                    if not error_details:
                        error_details.append("empty_response")
                        message = "empty_response"

            duration_ms = max(0, int((time.perf_counter() - started_target) * 1000))
            error_str = _truncate(error_details[0]) if error_details else None
            try:
                interval_sec = max(60, int(target.get("interval_sec") or 1800))
            except Exception:
                interval_sec = 1800

            result_row: Dict[str, Any] = {
                "target_id": target_id,
                "label": label,
                "url": url,
                "domain": domain,
                "ok": bool(ok),
                "status": int(status_code or (200 if ok else 0)),
                "error": error_str,
                "message": _truncate(message),
                "pages": pages,
                "new_items": new_items,
                "duration_ms": duration_ms,
                "last_run_ts": run_ts,
                "interval_sec": interval_sec,
                "next_run_ts": run_ts + interval_sec,
                "tags": list(target.get("tags") or []),
                "trust": trust_val,
            }
            if len(error_details) > 1:
                result_row["error_details"] = [_truncate(e) for e in error_details[:3]]
            results.append(result_row)

            target["last_run_ts"] = run_ts
            target["last_status"] = {
                "ok": bool(ok),
                "status": result_row["status"],
                "error": error_str,
                "message": result_row["message"],
                "pages": pages,
                "new_items": new_items,
                "duration_ms": duration_ms,
                "errors": len(error_details),
                "trust": trust_val,
            }

        _save_targets(targets)
        _save_crawled_index(idx)

        failure_count = sum(1 for row in results if not row.get("ok"))
        success_count = len(results) - failure_count
        overall_ok = success_count > 0 or not results
        if not results:
            message = "no_targets_processed"
        elif failure_count and success_count:
            message = "partial_failures"
        elif failure_count and not success_count:
            message = "all_failed"
        else:
            message = "ok"

        response: Dict[str, Any] = {
            "ok": overall_ok,
            "message": message,
            "results": results,
            "errors": failure_count,
            "fetched": stats["fetched"],
            "saved": stats["saved"],
            "targets_processed": len(results),
            "targets_selected": len(selected_targets),
            "skipped_targets": max(0, total_targets - len(selected_targets)),
        }

        if not overall_ok:
            response.setdefault(
                "error",
                "all_targets_failed" if failure_count and not success_count else "crawler_run_failed",
            )
        if triggered_topics:
            response["context_change"] = sorted(set(triggered_topics))

        return _finalize_response(response, selected_count=len(selected_targets))


def detect_critical_context(tags: List[str]) -> bool:
    """Heuristic: if any of the critical keywords are present, trigger reaction."""
    if not tags:
        return False
    critical = {"gesetz", "krieg", "gefahr", "notstand", "krise", "warnung"}
    return any((t or "").lower() in critical for t in tags)


def run_crawler_loop(interval_seconds: int = 3600):
    while True:
        try:
            run_crawler_once()
            promote_crawled_to_blocks()
        except Exception:
            pass
        time.sleep(interval_seconds)
