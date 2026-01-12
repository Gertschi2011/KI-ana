from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from netapi.deps import get_current_user_opt

router = APIRouter(prefix="/api/v2/learning", tags=["learning-v2"])


class ConsentDecisionIn(BaseModel):
    candidate_id: str = Field(min_length=3, max_length=120)
    decision: Literal["accept", "deny"]
    notes: Optional[str] = Field(default=None, max_length=500)


class ConsentDecisionOut(BaseModel):
    ok: bool
    applied: bool
    persisted_block_id: Optional[str] = None
    addressbook_updated: bool = False


@router.post("/consent", response_model=ConsentDecisionOut)
def consent_decision(
    body: ConsentDecisionIn,
    current=Depends(get_current_user_opt),
):
    if not current:
        raise HTTPException(401, "Unauthorized")

    try:
        user_id = int(current.get("id"))
    except Exception:
        raise HTTPException(401, "Unauthorized")

    from netapi.learning.candidates import get_learning_candidate_store

    store = get_learning_candidate_store()
    cand = store.get(body.candidate_id)
    if not cand:
        raise HTTPException(404, "Unknown candidate_id")
    if int(cand.user_id) != user_id:
        raise HTTPException(403, "Candidate does not belong to user")

    decision = str(body.decision).lower().strip()

    # Idempotent decisions
    if decision == "accept" and cand.status == "accepted":
        return ConsentDecisionOut(
            ok=True,
            applied=False,
            persisted_block_id=cand.persisted_block_id,
            addressbook_updated=bool(cand.addressbook_updated),
        )
    if decision == "deny" and cand.status == "denied":
        return ConsentDecisionOut(ok=True, applied=False, persisted_block_id=None, addressbook_updated=False)

    if cand.status in {"accepted", "denied"}:
        # Can't flip decisions (deterministic, no hidden side effects)
        return ConsentDecisionOut(
            ok=True,
            applied=False,
            persisted_block_id=cand.persisted_block_id,
            addressbook_updated=bool(cand.addressbook_updated),
        )

    # Apply decision
    if decision == "deny":
        cand.status = "denied"
        cand.decided_at = int(__import__("time").time())
        cand.persisted_block_id = None
        cand.addressbook_updated = False
        return ConsentDecisionOut(ok=True, applied=True, persisted_block_id=None, addressbook_updated=False)

    # decision == accept
    try:
        from netapi import memory_store
    except Exception as exc:  # pragma: no cover
        raise HTTPException(500, f"memory_store unavailable: {exc}") from exc

    topic = (cand.topic or (cand.snapshot.get("topic") if isinstance(cand.snapshot, dict) else "") or "").strip()
    safe_content = (cand.content or "").strip()

    # Safe-by-default: store only the correction content (no raw history/attachments)
    meta: Dict[str, Any] = {
        "type": "learning_correction",
        "user_id": int(user_id),
        "source": str(cand.source or "chat"),
        "topic": topic,
        "content": safe_content,
        "evidence": cand.snapshot.get("evidence") if isinstance(cand.snapshot, dict) else None,
        "candidate_id": cand.candidate_id,
        "notes": (body.notes or "").strip() or None,
        "created_at": cand.created_at,
        "decided_at": int(__import__("time").time()),
    }

    title = f"Learning Correction: user={user_id}{(' topic=' + topic) if topic else ''}"[:160]
    tags = ["learning_correction", f"user:{user_id}", "source:chat"]
    if topic:
        tags.append(f"topic:{topic[:60]}")

    block_id = memory_store.add_block(title=title, content=safe_content, tags=tags, meta=meta)

    addressbook_updated = False
    try:
        from netapi.core import addressbook

        addressbook.index_learning_correction(
            user_id=int(user_id),
            topic=topic or "unsorted",
            source=str(cand.source or "chat"),
            block_id=str(block_id),
        )
        addressbook_updated = True
    except Exception:
        addressbook_updated = False

    cand.status = "accepted"
    cand.decided_at = int(__import__("time").time())
    cand.persisted_block_id = str(block_id)
    cand.addressbook_updated = bool(addressbook_updated)

    return ConsentDecisionOut(
        ok=True,
        applied=True,
        persisted_block_id=str(block_id),
        addressbook_updated=bool(addressbook_updated),
    )


@router.get("/candidates")
def list_candidates(
    status: str = Query(default="pending"),
    limit: int = Query(default=50, ge=1, le=200),
    current=Depends(get_current_user_opt),
) -> Dict[str, Any]:
    if not current:
        raise HTTPException(401, "Unauthorized")

    try:
        user_id = int(current.get("id"))
    except Exception:
        raise HTTPException(401, "Unauthorized")

    st = (status or "").strip().lower()
    if st not in {"pending", "accepted", "denied", "all"}:
        raise HTTPException(400, "Invalid status")

    from netapi.learning.candidates import get_learning_candidate_store

    store = get_learning_candidate_store()
    items = store.list_for_user(user_id=user_id, status=None if st == "all" else st, limit=int(limit))

    public: List[Dict[str, Any]] = [c.to_public_dict() for c in items]
    return {"ok": True, "items": public}
