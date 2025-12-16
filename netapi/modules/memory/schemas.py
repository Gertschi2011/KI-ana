from __future__ import annotations

from typing import Any, Dict, List, Optional

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
