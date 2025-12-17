from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


def normalize_domain(value: str) -> Optional[str]:
    raw = (value or "").strip().lower()
    if not raw:
        return None

    # Remove scheme
    for prefix in ("https://", "http://"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break

    # Remove path/query/fragment
    raw = raw.split("/", 1)[0]
    raw = raw.split("?", 1)[0]
    raw = raw.split("#", 1)[0]

    # Strip common subdomain
    if raw.startswith("www."):
        raw = raw[4:]

    raw = raw.strip(". ")
    if not raw:
        return None

    # Very small sanity check
    if "." not in raw:
        return None

    return raw


class UserSourcePrefsBlock(BaseModel):
    type: str = Field(default="user_source_prefs")
    user_id: int
    country: str = Field(min_length=2, max_length=2)
    lang: str = Field(min_length=2, max_length=12)
    intent: str = Field(default="news")

    preferred_sources: List[str] = Field(default_factory=list)
    blocked_sources: List[str] = Field(default_factory=list)

    trust_overrides: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def normalized(self) -> "UserSourcePrefsBlock":
        preferred = []
        for item in self.preferred_sources or []:
            dom = normalize_domain(item)
            if dom and dom not in preferred:
                preferred.append(dom)

        blocked = []
        for item in self.blocked_sources or []:
            dom = normalize_domain(item)
            if dom and dom not in blocked:
                blocked.append(dom)

        return self.copy(update={
            "country": (self.country or "").strip().upper()[:2],
            "lang": (self.lang or "").strip().lower(),
            "intent": (self.intent or "news").strip().lower(),
            "preferred_sources": preferred,
            "blocked_sources": blocked,
        })


class SourceTrustProfileBlock(BaseModel):
    type: str = Field(default="source_trust_profile")
    user_id: int
    country: str = Field(min_length=2, max_length=2)
    mode: str = Field(default="news")

    domain_stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    updated_at: Optional[str] = None
    last_asked_at: Optional[str] = None
    last_feedback_at: Optional[str] = None

    def normalized(self) -> "SourceTrustProfileBlock":
        stats: Dict[str, Dict[str, Any]] = {}
        for raw_domain, raw_entry in (self.domain_stats or {}).items():
            dom = normalize_domain(str(raw_domain))
            if not dom:
                continue
            entry = dict(raw_entry) if isinstance(raw_entry, dict) else {}
            # Keep only expected keys (allow forwards-compatible extras)
            try:
                entry["weight"] = float(entry.get("weight") or 0.9)
            except Exception:
                entry["weight"] = 0.9
            for k in ("seen", "clicked", "downvotes", "upvotes"):
                try:
                    entry[k] = int(entry.get(k) or 0)
                except Exception:
                    entry[k] = 0
            if entry["weight"] < 0.0:
                entry["weight"] = 0.0
            stats[dom] = entry

        return self.copy(update={
            "country": (self.country or "").strip().upper()[:2],
            "mode": (self.mode or "news").strip().lower() or "news",
            "domain_stats": stats,
        })


class InterestProfileBlock(BaseModel):
    type: Literal["interest_profile"] = "interest_profile"

    user_id: int
    country: str = Field(min_length=2, max_length=2)
    lang: str = Field(min_length=2, max_length=12)
    mode: str = Field(default="news")

    category_weights: Dict[str, float] = Field(default_factory=dict)
    domain_affinity: Dict[str, float] = Field(default_factory=dict)
    signals_count: Dict[str, int] = Field(default_factory=lambda: {
        "explicit_up": 0,
        "explicit_down": 0,
        "implicit_positive": 0,
        "implicit_negative": 0,
    })
    last_signal_at: Optional[str] = None
    updated_at: Optional[str] = None

    def normalized(self) -> "InterestProfileBlock":
        cats: Dict[str, float] = {}
        for k, v in (self.category_weights or {}).items():
            kk = str(k or "").strip().lower()
            if not kk:
                continue
            try:
                cats[kk] = float(v)
            except Exception:
                continue

        doms: Dict[str, float] = {}
        for k, v in (self.domain_affinity or {}).items():
            dom = normalize_domain(str(k))
            if not dom:
                continue
            try:
                doms[dom] = float(v)
            except Exception:
                continue

        counts = dict(self.signals_count or {})
        for key in ("explicit_up", "explicit_down", "implicit_positive", "implicit_negative"):
            try:
                counts[key] = int(counts.get(key) or 0)
            except Exception:
                counts[key] = 0

        return self.copy(update={
            "country": (self.country or "").strip().upper()[:2],
            "lang": (self.lang or "").strip().lower(),
            "mode": (self.mode or "news").strip().lower() or "news",
            "category_weights": cats,
            "domain_affinity": doms,
            "signals_count": counts,
        })


def now_iso_z() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
