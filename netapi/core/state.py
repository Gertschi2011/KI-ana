from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import json
import os
from pathlib import Path
import logging
import traceback

# Soft memory store import
try:
    from netapi import memory_store as _mem  # type: ignore
except Exception:
    _mem = None  # type: ignore

STATE_RUNTIME_PATH = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))) / "runtime" / "kiana_state.json"
logger = logging.getLogger(__name__)

@dataclass
class PendingLearningItem:
    topic: str
    fact: str
    source: str  # "user", "web"
    created_at: str
    confidence: float = 0.5
    uses: int = 0


@dataclass
class KianaState:
    created_at: str
    last_active_at: str
    # Primary affective state
    mood: str = "verspielt"
    energy: float = 70.0  # 0..100
    # Fine-grained needs
    rest: float = 0.7         # 0..1
    curiosity: float = 0.9    # 0..1
    connection: float = 0.5   # 0..1
    needs: Dict[str, float] = field(default_factory=lambda: {"curiosity": 0.9, "connection": 0.5, "rest": 0.7})
    goals: List[str] = field(default_factory=list)
    recent_topics: List[str] = field(default_factory=list)
    cycles: int = 0
    learning_buffer: List[PendingLearningItem] = field(default_factory=list)
    pending_followup: Optional[str] = None
    pending_learning: Optional[Dict[str, Any]] = None  # {"topic_path": str}
    # Controlled Freedom mode: when True, Kiana may explore (web, reflective line)
    mode_explore: bool = False
    # Sleep tracking
    last_sleep_at: Optional[str] = None
    is_sleeping: bool = False
    # User interaction affect
    last_user_tone: str = "neutral"  # freundlich | neutral | kühl | hart
    user_style_preference: Optional[str] = None  # sachlich | locker | None

    @staticmethod
    def new() -> "KianaState":
        now = datetime.now(timezone.utc).isoformat()
        return KianaState(created_at=now, last_active_at=now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "KianaState":
        if not d:
            return KianaState.new()
        # Rehydrate learning buffer if present
        lb_raw = list(d.get("learning_buffer") or [])
        lb: List[PendingLearningItem] = []
        for it in lb_raw:
            try:
                lb.append(PendingLearningItem(
                    topic=str(it.get("topic") or ""),
                    fact=str(it.get("fact") or ""),
                    source=str(it.get("source") or "user"),
                    created_at=str(it.get("created_at") or datetime.now(timezone.utc).isoformat()),
                    confidence=float(it.get("confidence") or 0.5),
                    uses=int(it.get("uses") or 0),
                ))
            except Exception:
                continue
        return KianaState(
            created_at=str(d.get("created_at") or datetime.now(timezone.utc).isoformat()),
            last_active_at=str(d.get("last_active_at") or datetime.now(timezone.utc).isoformat()),
            mood=str(d.get("mood") or "verspielt"),
            energy=float(d.get("energy") or 70.0),
            rest=float(d.get("rest") or d.get("needs",{}).get("rest", 0.7)),
            curiosity=float(d.get("curiosity") or d.get("needs",{}).get("curiosity", 0.9)),
            connection=float(d.get("connection") or d.get("needs",{}).get("connection", 0.5)),
            needs=dict(d.get("needs") or {"curiosity": 0.9, "connection": 0.5, "rest": 0.7}),
            goals=list(d.get("goals") or []),
            recent_topics=list(d.get("recent_topics") or []),
            cycles=int(d.get("cycles") or 0),
            learning_buffer=lb,
            pending_followup=(d.get("pending_followup") if d.get("pending_followup") is not None else None),
            pending_learning=(d.get("pending_learning") if d.get("pending_learning") is not None else None),
            mode_explore=bool(d.get("mode_explore", False)),
            last_sleep_at=(d.get("last_sleep_at") if d.get("last_sleep_at") else None),
            is_sleeping=bool(d.get("is_sleeping", False)),
            last_user_tone=str(d.get("last_user_tone") or "neutral"),
            user_style_preference=(d.get("user_style_preference") if d.get("user_style_preference") else None),
        )

    # ---- Life-state updates ----
    def update_from_event(self, event_type: str, topic: Optional[str] = None) -> None:
        try:
            if event_type == "user_message":
                self.energy = max(0, int(self.energy) - 1)
                if topic:
                    t = str(topic).strip()
                    if t and (t not in self.recent_topics):
                        self.needs["curiosity"] = min(1.0, float(self.needs.get("curiosity", 0.5)) + 0.10)
                        try:
                            self.recent_topics.append(t)
                            if len(self.recent_topics) > 20:
                                self.recent_topics = self.recent_topics[-20:]
                        except Exception:
                            pass
            elif event_type in ("idle", "smalltalk_light"):
                self.energy = min(100, int(round(float(self.energy) + 0.5)))
                self.needs["rest"] = max(0.0, float(self.needs.get("rest", 0.5)) - 0.05)
        except Exception:
            return

    def derive_mood(self) -> str:
        try:
            e = int(self.energy)
            curiosity = float(self.needs.get("curiosity", 0.5))
            if e >= 70 and curiosity >= 0.6:
                return "verspielt"
            if e <= 30:
                return "ruhig / müde"
            return self.mood or "neugierig"
        except Exception:
            return self.mood or "neugierig"


def _read_runtime_state() -> Optional[Dict[str, Any]]:
    try:
        if STATE_RUNTIME_PATH.exists():
            return json.loads(STATE_RUNTIME_PATH.read_text(encoding="utf-8") or "{}")
    except Exception:
        return None
    return None

def _write_runtime_state(data: Dict[str, Any]) -> None:
    try:
        STATE_RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_RUNTIME_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_state() -> KianaState:
    # Prefer runtime file
    d = _read_runtime_state() or {}
    if d:
        return KianaState.from_dict(d)
    # Try memory store last block
    try:
        if _mem is not None:
            bid = _mem.find_last_block_by_tag("kiana_state")  # type: ignore[attr-defined]
            if bid:
                blk = _mem.get_block(bid)
                if blk and isinstance(blk.get("content"), str):
                    return KianaState.from_dict(json.loads(blk["content"]))
    except Exception:
        pass
    return KianaState.new()


def save_state(st: KianaState) -> None:
    try:
        data = st.to_dict()
        _write_runtime_state(data)
        try:
            if _mem is not None:
                _mem.add_block(
                    title="KI_ana Self-State",
                    content=json.dumps(data, ensure_ascii=False),
                    tags=["kiana_state"],
                    url=None,
                    meta={"ts": int(datetime.now(timezone.utc).timestamp())},
                )
        except Exception as e:
            logger.error("save_state: write to memory_store failed: %s", e)
            try:
                logger.debug(traceback.format_exc())
            except Exception:
                pass
    except Exception as e:
        logger.error("save_state failed: %s", e)
        try:
            logger.debug(traceback.format_exc())
        except Exception:
            pass


def save_experience(user_id: Optional[int], conversation_id: Optional[int], data: Dict[str, Any]) -> None:
    try:
        if _mem is None:
            return
        meta = {"user_id": user_id, "conversation_id": conversation_id}
        _mem.add_block(
            title=f"Experience {data.get('timestamp','')}",
            content=json.dumps(data, ensure_ascii=False),
            tags=["experience"],
            url=None,
            meta=meta,
        )
    except Exception:
        pass


def get_relevant_experiences(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Return compact summaries of relevant experiences."""
    out: List[Dict[str, Any]] = []
    try:
        if _mem is None:
            return []
        # Try vector search if available
        try:
            sem = _mem.search_blocks_semantic(query, top_k=limit, min_score=0.15)  # type: ignore[attr-defined]
            for bid, sc in sem:
                b = _mem.get_block(bid)
                if not b:
                    continue
                out.append({
                    "id": bid,
                    "title": b.get("title",""),
                    "content": b.get("content",""),
                    "score": float(sc),
                })
            if out:
                return out[:limit]
        except Exception:
            pass
        # Fallback: keyword scan
        blocks = _mem.search_blocks(keyword=query, limit=limit, tags=["experience"])  # type: ignore[attr-defined]
        for b in blocks or []:
            out.append({"id": b.get("id"), "title": b.get("title",""), "content": b.get("content",""), "score": 0.0})
    except Exception:
        return []
    return out[:limit]


def summarize_experiences(exps: List[Dict[str, Any]], max_lines: int = 5) -> str:
    lines: List[str] = []
    for e in exps[:max_lines]:
        try:
            content = e.get("content") or ""
            if isinstance(content, str):
                j = json.loads(content)
            else:
                j = content
            um = (j.get("user_message") or "").strip()
            ar = (j.get("assistant_reply") or "").strip()
            if um or ar:
                lines.append(f"- Nutzer fragte: {um[:140]} | Du antwortetest: {ar[:140]}")
        except Exception:
            continue
    return "\n".join(lines)


def add_learning_item(state: KianaState, topic: str, fact: str, source: str = "user", ts: Optional[str] = None) -> None:
    """Append a new PendingLearningItem to state's learning_buffer (bounded)."""
    try:
        when = ts or datetime.now(timezone.utc).isoformat()
    except Exception:
        from datetime import datetime as _dt
        when = _dt.utcnow().isoformat() + "Z"
    try:
        item = PendingLearningItem(
            topic=str(topic or ""),
            fact=str(fact or ""),
            source=str(source or "user"),
            created_at=str(when),
            confidence=0.5,
            uses=0,
        )
        if not hasattr(state, "learning_buffer") or state.learning_buffer is None:
            state.learning_buffer = []
        state.learning_buffer.append(item)
        # Keep buffer small
        try:
            MAX_BUF = 50
            if len(state.learning_buffer) > MAX_BUF:
                state.learning_buffer = state.learning_buffer[-MAX_BUF:]
        except Exception:
            pass
    except Exception:
        # Do not raise from helper
        return


async def reflect_if_needed(state: KianaState, recent_exps: List[Dict[str, Any]]) -> None:
    try:
        if state.cycles % 10 != 0:
            return
        # Build simple reflection prompt and store
        from netapi.modules.chat.router import call_llm_once  # lazy import
        now = datetime.now(timezone.utc).isoformat()
        summary = summarize_experiences(recent_exps, max_lines=5)
        prompt = (
            "Du bist Kiana. Dies sind einige deiner letzten Erfahrungen:\n"
            f"{summary}\n\n"
            "Reflektiere kurz und knapp (3-5 Sätze):\n"
            "- Was hast du über den Nutzer gelernt?\n"
            "- Was hast du über dich selbst gelernt?\n"
            "- Was könntest du beim nächsten Mal besser machen?"
        )
        sys = "Kurze Reflexion, deutsch, prägnant."
        txt = await call_llm_once(prompt, sys, lang="de-DE", persona="friendly")
        if _mem is not None:
            _mem.add_block(
                title="KI_ana Reflexion",
                content=str(txt or "").strip(),
                tags=["reflection"],
                url=None,
                meta={"ts": int(datetime.now(timezone.utc).timestamp())},
            )
    except Exception:
        return
