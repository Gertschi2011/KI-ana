from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

_KI_ROOT = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
TARGETS_PATH = _KI_ROOT / "system" / "crawler_targets.json"
_LEGACY_SOURCES_PATH = _KI_ROOT / "system" / "crawl_sources.json"

_DEFAULT_TARGETS: List[Dict[str, Any]] = [
    # Interne Hilfeseiten
    {
        "id": "internal-help",
        "label": "KI_ana Hilfe",
        "url": "https://ki-ana.at/static/help.html",
        "enabled": True,
        "interval_sec": 86400,
        "last_run_ts": 0,
        "last_status": None,
        "tags": ["internal", "docs"],
        "trust": 0.95,
    },
    {
        "id": "internal-skills",
        "label": "KI_ana Skills",
        "url": "https://ki-ana.at/static/skills.html",
        "enabled": True,
        "interval_sec": 86400,
        "last_run_ts": 0,
        "last_status": None,
        "tags": ["internal", "docs"],
        "trust": 0.95,
    },
    # Cybercrime / Security Awareness
    {
        "id": "cybercrime-bmi",
        "label": "BMI – Cybercrime Prävention",
        "url": "https://www.bmi.gv.at/sicherundfairnetzt/Cybercrime_Digitale_Sicherheit_Gewaltpraevention.aspx",
        "enabled": True,
        "interval_sec": 21600,
        "last_run_ts": 0,
        "last_status": None,
        "tags": ["cybercrime", "security", "austria"],
        "trust": 0.85,
    },
    {
        "id": "cybercrime-europol",
        "label": "Europol – Cybercrime",
        "url": "https://www.europol.europa.eu/crime-areas-and-trends/crime-areas/cybercrime",
        "enabled": True,
        "interval_sec": 21600,
        "last_run_ts": 0,
        "last_status": None,
        "tags": ["cybercrime", "security", "eu"],
        "trust": 0.9,
    },
    {
        "id": "cybercrime-enisa",
        "label": "ENISA – Cybersecurity",
        "url": "https://www.enisa.europa.eu/topics/cs-awareness",
        "enabled": True,
        "interval_sec": 28800,
        "last_run_ts": 0,
        "last_status": None,
        "tags": ["cybercrime", "security", "eu"],
        "trust": 0.9,
    },
    {
        "id": "cybercrime-nomoreransom",
        "label": "NoMoreRansom",
        "url": "https://www.nomoreransom.org/en/index.html",
        "enabled": True,
        "interval_sec": 28800,
        "last_run_ts": 0,
        "last_status": None,
        "tags": ["cybercrime", "security"],
        "trust": 0.85,
    },
    {
        "id": "cybercrime-bka",
        "label": "BKA DE – Cybercrime",
        "url": "https://www.bka.de/DE/ThemenABisZ/ComputerKriminalitaet/cybercrime_node.html",
        "enabled": True,
        "interval_sec": 28800,
        "last_run_ts": 0,
        "last_status": None,
        "tags": ["cybercrime", "security", "de"],
        "trust": 0.85,
    },
    # Nachrichtenquellen
    {
        "id": "news-bbc-world",
        "label": "BBC News – World",
        "url": "https://www.bbc.com/news/world",
        "enabled": True,
        "interval_sec": 7200,
        "last_run_ts": 0,
        "last_status": None,
        "tags": ["news", "world", "english"],
        "trust": 0.7,
    },
    {
        "id": "news-aljazeera",
        "label": "Al Jazeera – News",
        "url": "https://www.aljazeera.com/news/",
        "enabled": True,
        "interval_sec": 7200,
        "last_run_ts": 0,
        "last_status": None,
        "tags": ["news", "world", "english"],
        "trust": 0.7,
    },
    {
        "id": "news-dw",
        "label": "Deutsche Welle – World",
        "url": "https://www.dw.com/en/top-stories/world/s-1429",
        "enabled": True,
        "interval_sec": 10800,
        "last_run_ts": 0,
        "last_status": None,
        "tags": ["news", "europe", "english"],
        "trust": 0.7,
    },
    {
        "id": "news-the-hindu",
        "label": "The Hindu – International",
        "url": "https://www.thehindu.com/news/international/",
        "enabled": True,
        "interval_sec": 10800,
        "last_run_ts": 0,
        "last_status": None,
        "tags": ["news", "asia", "english"],
        "trust": 0.65,
    },
]

_TARGETS_LOCK = threading.RLock()


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or f"target-{int(time.time())}"


def _ensure_parent_dir() -> None:
    TARGETS_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_legacy_sources() -> List[Dict[str, Any]]:
    if not _LEGACY_SOURCES_PATH.exists():
        return []
    try:
        data = json.loads(_LEGACY_SOURCES_PATH.read_text(encoding="utf-8")) or []
    except Exception:
        return []
    targets: List[Dict[str, Any]] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        label = str(item.get("title") or item.get("label") or url).strip() or url
        slug = _slugify(label)
        target = {
            "id": f"legacy-{slug or idx}",
            "label": label,
            "url": url,
            "enabled": bool(item.get("enabled", True)),
            "interval_sec": int(item.get("interval_sec") or 1800),
            "last_run_ts": 0,
            "last_status": None,
            "tags": list(item.get("tags") or []),
        }
        targets.append(target)
    return targets


def ensure_targets_file() -> None:
    with _TARGETS_LOCK:
        _ensure_parent_dir()
        existing: List[Dict[str, Any]] = []
        if TARGETS_PATH.exists():
            try:
                raw = json.loads(TARGETS_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    existing = [item for item in raw if isinstance(item, dict)]
            except Exception:
                existing = []
        else:
            existing = _load_legacy_sources()

        known_ids = {str(item.get("id")) for item in existing}
        appended = False
        for default in _DEFAULT_TARGETS:
            if str(default.get("id")) in known_ids:
                continue
            existing.append(dict(default))
            known_ids.add(str(default.get("id")))
            appended = True

        if not TARGETS_PATH.exists() or appended:
            TARGETS_PATH.write_text(
                json.dumps(existing or list(_DEFAULT_TARGETS), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


def load_targets() -> List[Dict[str, Any]]:
    ensure_targets_file()
    with _TARGETS_LOCK:
        try:
            data = json.loads(TARGETS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                cleaned: List[Dict[str, Any]] = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    cleaned.append(_normalize_target(item))
                return cleaned
        except Exception:
            pass
        return list(_DEFAULT_TARGETS)


def save_targets(targets: Iterable[Dict[str, Any]]) -> None:
    with _TARGETS_LOCK:
        _ensure_parent_dir()
        normalized = [_normalize_target(t) for t in targets if isinstance(t, dict)]
        TARGETS_PATH.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=False),
            encoding="utf-8",
        )


def generate_target_id(label: str, existing: Iterable[str] | None = None) -> str:
    base = _slugify(label)
    existing_set = {str(x) for x in (existing or []) if x}
    candidate = base or "target"
    suffix = 1
    while candidate in existing_set:
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def _normalize_target(raw: Dict[str, Any]) -> Dict[str, Any]:
    target = dict(raw)
    target["id"] = str(target.get("id") or generate_target_id(str(target.get("label") or "target"), []))
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
    last_status = target.get("last_status")
    if last_status is not None and not isinstance(last_status, dict):
        last_status = {"message": str(last_status)}
    target["last_status"] = last_status
    tags = target.get("tags")
    if isinstance(tags, (list, tuple)):
        clean_tags = []
        for t in tags:
            st = str(t or "").strip()
            if st and st not in clean_tags:
                clean_tags.append(st)
        target["tags"] = clean_tags
    else:
        target["tags"] = []

    trust_val = target.get("trust")
    if trust_val is not None:
        try:
            trust_float = float(trust_val)
            if trust_float < 0.0:
                trust_float = 0.0
            if trust_float > 1.0:
                trust_float = 1.0
            target["trust"] = trust_float
        except Exception:
            target.pop("trust", None)

    return target


def update_target_status(targets: List[Dict[str, Any]], target_id: str, status: Dict[str, Any]) -> bool:
    matched = False
    now_ts = int(time.time())
    for item in targets:
        if str(item.get("id")) != str(target_id):
            continue
        matched = True
        item["last_run_ts"] = int(status.get("last_run_ts") or now_ts)
        item["last_status"] = {k: v for k, v in status.items() if k != "last_run_ts"}
        break
    if matched:
        save_targets(targets)
    return matched


__all__ = [
    "TARGETS_PATH",
    "ensure_targets_file",
    "load_targets",
    "save_targets",
    "generate_target_id",
    "update_target_status",
]
