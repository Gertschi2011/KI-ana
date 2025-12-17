from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import re
import time

# Reuse the same file used elsewhere
ADDRBOOK_PATH = Path(__file__).resolve().parents[2] / "memory" / "index" / "addressbook.json"
BLOCKS_ROOT = Path(__file__).resolve().parents[2] / "memory" / "long_term" / "blocks"


def _now_ts() -> int:
    return int(time.time())


def _prefs_key(user_id: int, country: str, lang: str, intent: str) -> str:
    return f"prefs:sources:{int(user_id)}:{(country or '').strip().upper()[:2]}:{(lang or '').strip().lower()}:{(intent or 'news').strip().lower()}"


def _trust_key(user_id: int, country: str, mode: str) -> str:
    mode_norm = (mode or "news").strip().lower() or "news"
    return f"trust:sources:{int(user_id)}:{(country or '').strip().upper()[:2]}:{mode_norm}"


def _user_settings_key(user_id: int) -> str:
    return f"user_settings:{int(user_id)}"


def _interest_key(user_id: int, country: str, lang: str, mode: str) -> str:
    mode_norm = (mode or "news").strip().lower() or "news"
    return f"interest_profile:{int(user_id)}:{(country or '').strip().upper()[:2]}:{(lang or '').strip().lower()}:{mode_norm}"


def _normalize_domain(value: str) -> Optional[str]:
    raw = (value or "").strip().lower()
    if not raw:
        return None
    for prefix in ("https://", "http://"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    raw = raw.split("/", 1)[0]
    raw = raw.split("?", 1)[0]
    raw = raw.split("#", 1)[0]
    if raw.startswith("www."):
        raw = raw[4:]
    raw = raw.strip(". ")
    if not raw or "." not in raw:
        return None
    return raw


def _normalize_domain_list(values: Optional[List[str]]) -> List[str]:
    out: List[str] = []
    for item in values or []:
        dom = _normalize_domain(str(item))
        if dom and dom not in out:
            out.append(dom)
    return out


def _normalize_source_prefs_index(data: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("source_prefs"), dict):
        return data.get("source_prefs") or {}
    return {}


def _normalize_source_trust_index(data: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("source_trust_profiles"), dict):
        return data.get("source_trust_profiles") or {}
    return {}


def _normalize_user_settings_index(data: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("user_settings"), dict):
        return data.get("user_settings") or {}
    return {}


def _normalize_interest_profiles_index(data: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("interest_profiles"), dict):
        return data.get("interest_profiles") or {}
    return {}


def index_user_settings(
    *,
    block_id: str,
    user_id: int,
    proactive_news_enabled: bool = False,
    updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    data = _load()
    idx = _normalize_user_settings_index(data)
    key = _user_settings_key(user_id)
    entry = {
        "user_id": int(user_id),
        "proactive_news_enabled": bool(proactive_news_enabled),
        "updated_at": updated_at or str(_now_ts()),
        "block_id": str(block_id),
    }
    idx[key] = entry
    data["user_settings"] = idx

    ADDRBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    ADDRBOOK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def get_user_settings(*, user_id: int) -> Optional[str]:
    data = _load()
    idx = _normalize_user_settings_index(data)
    key = _user_settings_key(user_id)
    entry = idx.get(key)
    if not isinstance(entry, dict):
        return None
    block_id = entry.get("block_id")
    return str(block_id) if block_id else None


def index_interest_profile(
    *,
    block_id: str,
    user_id: int,
    country: str,
    lang: str,
    mode: str,
    updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    data = _load()
    idx = _normalize_interest_profiles_index(data)
    key = _interest_key(user_id, country, lang, mode)
    entry = {
        "user_id": int(user_id),
        "country": (country or "").strip().upper()[:2],
        "lang": (lang or "").strip().lower(),
        "mode": (mode or "news").strip().lower() or "news",
        "updated_at": updated_at or str(_now_ts()),
        "block_id": str(block_id),
    }
    idx[key] = entry
    data["interest_profiles"] = idx

    ADDRBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    ADDRBOOK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def get_interest_profile(
    *,
    user_id: int,
    country: str,
    lang: str,
    mode: str,
) -> Optional[str]:
    data = _load()
    idx = _normalize_interest_profiles_index(data)
    key = _interest_key(user_id, country, lang, mode)
    entry = idx.get(key)
    if not isinstance(entry, dict):
        return None
    block_id = entry.get("block_id")
    return str(block_id) if block_id else None


def index_source_trust_profile(
    *,
    block_id: str,
    user_id: int,
    country: str,
    mode: str,
    domain_count: int = 0,
    updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Index a source_trust_profile block for fast retrieval.

    Stores under a dedicated key: trust:sources:{user_id}:{country}:{mode}
    """
    data = _load()
    trust = _normalize_source_trust_index(data)

    key = _trust_key(user_id, country, mode)
    entry = {
        "user_id": int(user_id),
        "country": (country or "").strip().upper()[:2],
        "mode": (mode or "news").strip().lower() or "news",
        "domain_count": int(domain_count or 0),
        "updated_at": updated_at or str(_now_ts()),
        "block_id": str(block_id),
    }
    trust[key] = entry
    data["source_trust_profiles"] = trust

    ADDRBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    ADDRBOOK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def get_source_trust_profile(
    *,
    user_id: int,
    country: str,
    mode: str,
) -> Optional[str]:
    data = _load()
    trust = _normalize_source_trust_index(data)
    key = _trust_key(user_id, country, mode)
    entry = trust.get(key)
    if not isinstance(entry, dict):
        return None
    block_id = entry.get("block_id")
    return str(block_id) if block_id else None


def get_source_trust_profile_entry(
    *,
    user_id: int,
    country: str,
    mode: str,
) -> Optional[Dict[str, Any]]:
    data = _load()
    trust = _normalize_source_trust_index(data)
    key = _trust_key(user_id, country, mode)
    entry = trust.get(key)
    return entry if isinstance(entry, dict) else None


def index_source_prefs(
    *,
    block_id: str,
    user_id: int,
    country: str,
    lang: str,
    intent: str,
    preferred: Optional[List[str]] = None,
    blocked: Optional[List[str]] = None,
    trust_overrides: Optional[Dict[str, Any]] = None,
    updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Index a user_source_prefs block for fast retrieval.

    Stores under a dedicated key: prefs:sources:{user_id}:{country}:{lang}:{intent}
    """
    data = _load()
    prefs = _normalize_source_prefs_index(data)

    key = _prefs_key(user_id, country, lang, intent)
    entry = {
        "user_id": int(user_id),
        "country": (country or "").strip().upper()[:2],
        "lang": (lang or "").strip().lower(),
        "intent_tags": [str(intent or "news").strip().lower()],
        "preferred": _normalize_domain_list(preferred),
        "blocked": _normalize_domain_list(blocked),
        "trust_overrides": trust_overrides or {},
        "updated_at": updated_at or str(_now_ts()),
        "block_id": str(block_id),
    }
    prefs[key] = entry
    data["source_prefs"] = prefs

    ADDRBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    ADDRBOOK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def get_source_prefs(
    *,
    user_id: int,
    country: str,
    lang: str,
    intent: str,
) -> Optional[str]:
    data = _load()
    prefs = _normalize_source_prefs_index(data)
    key = _prefs_key(user_id, country, lang, intent)
    entry = prefs.get(key)
    if not isinstance(entry, dict):
        return None
    block_id = entry.get("block_id")
    return str(block_id) if block_id else None


def get_source_prefs_entry(
    *,
    user_id: int,
    country: str,
    lang: str,
    intent: str,
) -> Optional[Dict[str, Any]]:
    data = _load()
    prefs = _normalize_source_prefs_index(data)
    key = _prefs_key(user_id, country, lang, intent)
    entry = prefs.get(key)
    return entry if isinstance(entry, dict) else None


def _load() -> Dict[str, Any]:
    try:
        if ADDRBOOK_PATH.exists():
            return json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8") or "{}")
    except Exception:
        pass
    return {"blocks": [], "source_prefs": {}, "source_trust_profiles": {}, "user_settings": {}, "interest_profiles": {}}


def _normalize_blocks(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("blocks"), list):
        return data.get("blocks") or []
    # legacy schema not needed here; router already migrates; keep fallback empty
    return []


def _topic_from_msg(msg: str) -> str:
    t = (msg or "").strip()
    # remove common German question heads
    heads = [
        r"^was\s+wei[ßs]t\s+du\s+über\s+",
        r"^erzähl\s+mir\s+etwas\s+über\s+",
        r"^wer\s+ist\s+",
        r"^was\s+ist\s+",
    ]
    low = t.lower()
    for h in heads:
        try:
            if re.match(h, low):
                # strip same length from original to keep case
                n = len(re.match(h, low).group(0))  # type: ignore
                return t[n:].strip().strip('?!. ').strip()
        except Exception:
            continue
    return t.strip('?!. ').strip()


def extract_topic_from_message(msg: str) -> str:
    return _topic_from_msg(msg)


def build_topic_paths(topic: str, msg: str = "") -> List[str]:
    topic = (topic or "").strip()
    if not topic:
        return []
    parts: List[str] = []
    low = (msg or topic).lower()
    # simple heuristics for media series
    if ("serie" in low) or ("staffel" in low):
        parts = ["Multimedia", "Serien", topic]
    else:
        parts = ["Wissen", "Allgemein", topic]
    return ["/".join(parts)]


def suggest_topic_paths(user_msg: str) -> List[str]:
    topic = extract_topic_from_message(user_msg)
    return build_topic_paths(topic, user_msg)


def find_paths_for_topic(topic: str) -> List[str]:
    topic_norm = (topic or "").strip().lower()[:120]
    data = _load()
    blocks = _normalize_blocks(data)
    paths: List[str] = []
    for b in blocks:
        try:
            t = str(b.get("topic") or "").strip().lower()[:120]
            if t != topic_norm:
                continue
            p = str(b.get("path") or "").strip()
            if not p:
                continue
            # Derive topic_path from stored file path
            # memory/long_term/blocks/<topic_path>/<block>.json
            try:
                rel = Path(p)
                if not rel.is_absolute():
                    rel = BLOCKS_ROOT / rel
                rel = rel.resolve()
                if BLOCKS_ROOT in rel.parents:
                    tp = str(rel.parent.relative_to(BLOCKS_ROOT)).replace("\\", "/")
                    if tp:
                        paths.append(tp)
            except Exception:
                continue
        except Exception:
            continue
    # De-duplicate, keep order
    seen = set()
    out: List[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def find_blocks_for_topic(topic: str) -> List[str]:
    topic_norm = (topic or "").strip().lower()[:120]
    data = _load()
    blocks = _normalize_blocks(data)
    ids: List[str] = []
    for b in blocks:
        try:
            t = str(b.get("topic") or "").strip().lower()[:120]
            if t != topic_norm:
                continue
            bid = str(b.get("block_id") or "").strip()
            if bid:
                ids.append(bid)
            else:
                # derive from path
                p = str(b.get("path") or "").strip()
                if p:
                    ids.append(Path(p).stem)
        except Exception:
            continue
    # de-dup
    seen = set()
    out: List[str] = []
    for i in ids:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def register_block_for_topic(topic_path: str, block_id: str) -> None:
    try:
        data = _load()
        blocks = _normalize_blocks(data)
        entry = {
            "topic": topic_path.split('/')[-1] if '/' in topic_path else topic_path,
            "block_id": block_id,
            "path": f"{topic_path}/{block_id}.json",
            "source": "",
            "timestamp": None,
            "rating": 0,
        }
        # append if not exists
        exists = False
        for b in blocks:
            if b.get("topic") == entry["topic"] and (b.get("block_id") == block_id):
                exists = True
                break
        if not exists:
            blocks.append(entry)
        ADDRBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
        ADDRBOOK_PATH.write_text(json.dumps({"blocks": blocks}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # best effort
        pass
