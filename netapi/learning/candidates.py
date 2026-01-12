from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_ts() -> int:
    return int(time.time())


def _is_test_mode() -> bool:
    return (os.getenv("TEST_MODE") or "").strip() == "1"


def _safe_str(value: Any, *, max_len: int) -> str:
    text = str(value or "").strip()
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


@dataclass
class LearningCandidate:
    candidate_id: str
    user_id: int
    status: str  # pending|accepted|denied
    created_at: int
    decided_at: Optional[int] = None
    snapshot: Dict[str, Any] = field(default_factory=dict)
    content: str = ""
    source: str = "chat"
    topic: str = ""
    persisted_block_id: Optional[str] = None
    addressbook_updated: bool = False

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "user_id": self.user_id,
            "status": self.status,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
            "snapshot": self.snapshot,
            "source": self.source,
            "topic": self.topic,
            "persisted_block_id": self.persisted_block_id,
        }


class LearningCandidateStore:
    """A small in-memory candidate store (ring-buffer-ish) for consent-based learning."""

    def __init__(self, *, max_items: int = 200):
        self._lock = threading.Lock()
        self._max_items = int(max_items or 200)
        self._counter = 0
        self._items: Dict[str, LearningCandidate] = {}
        self._order: List[str] = []

    def _new_id(self) -> str:
        self._counter += 1
        if _is_test_mode():
            return f"lc_{self._counter}"
        return f"lc_{_now_ms()}_{self._counter}"

    def create_candidate(
        self,
        *,
        user_id: int,
        content: str,
        snapshot: Optional[Dict[str, Any]] = None,
        source: str = "chat",
        topic: str = "",
    ) -> LearningCandidate:
        with self._lock:
            cid = self._new_id()
            candidate = LearningCandidate(
                candidate_id=cid,
                user_id=int(user_id),
                status="pending",
                created_at=_now_ts(),
                decided_at=None,
                snapshot=dict(snapshot or {}),
                content=_safe_str(content, max_len=800),
                source=str(source or "chat"),
                topic=_safe_str(topic, max_len=120),
            )
            self._items[cid] = candidate
            self._order.append(cid)
            # prune
            if len(self._order) > self._max_items:
                drop = self._order[:-self._max_items]
                self._order = self._order[-self._max_items:]
                for k in drop:
                    self._items.pop(k, None)
            return candidate

    def get(self, candidate_id: str) -> Optional[LearningCandidate]:
        with self._lock:
            return self._items.get(str(candidate_id or "").strip())

    def list_for_user(
        self,
        *,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[LearningCandidate]:
        uid = int(user_id)
        st = (status or "").strip().lower() or None
        lim = max(1, min(200, int(limit or 50)))
        with self._lock:
            out: List[LearningCandidate] = []
            for cid in reversed(self._order):
                item = self._items.get(cid)
                if not item:
                    continue
                if item.user_id != uid:
                    continue
                if st and item.status != st:
                    continue
                out.append(item)
                if len(out) >= lim:
                    break
            return out

    def stats(self) -> Dict[str, Any]:
        """Return small aggregate stats across all candidates (best-effort, in-memory)."""
        now = _now_ts()
        with self._lock:
            pending = 0
            accepted = 0
            denied = 0
            last_created = 0
            accepted_24h = 0
            denied_24h = 0
            cutoff_24h = now - 86400
            for cid in self._order:
                item = self._items.get(cid)
                if not item:
                    continue
                try:
                    last_created = max(last_created, int(item.created_at or 0))
                except Exception:
                    pass
                st = (item.status or "").strip().lower()
                if st == "pending":
                    pending += 1
                elif st == "accepted":
                    accepted += 1
                    try:
                        if int(item.decided_at or 0) >= cutoff_24h:
                            accepted_24h += 1
                    except Exception:
                        pass
                elif st == "denied":
                    denied += 1
                    try:
                        if int(item.decided_at or 0) >= cutoff_24h:
                            denied_24h += 1
                    except Exception:
                        pass

            return {
                "pending": int(pending),
                "accepted": int(accepted),
                "denied": int(denied),
                "accepted_24h": int(accepted_24h),
                "denied_24h": int(denied_24h),
                "last_candidate_ts": int(last_created or 0),
            }


_store: Optional[LearningCandidateStore] = None


def get_learning_candidate_store() -> LearningCandidateStore:
    global _store
    if _store is None:
        _store = LearningCandidateStore()
    return _store
