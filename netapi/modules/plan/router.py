from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import time, json

from ...deps import get_current_user_required, require_role
from ...db import SessionLocal
from ...models import Plan, PlanStep

try:
    from ..admin.router import write_audit  # type: ignore
except Exception:
    def write_audit(*args, **kwargs):  # type: ignore
        return None

router = APIRouter(prefix="/api/plan", tags=["planner"])

# --- Test-mode cleanup for deterministic planner tests ----------------------
def clear_plan_state():
    try:
        with SessionLocal() as db:
            # Delete steps first due to FK
            try:
                db.query(PlanStep).delete()
            except Exception:
                pass
            try:
                db.query(Plan).delete()
            except Exception:
                pass
            db.commit()
    except Exception:
        pass

@router.on_event("startup")
def _planner_testmode_reset():  # pragma: no cover (indirectly exercised in tests)
    import os
    try:
        if str(os.getenv("TEST_MODE", "")).strip() in {"1","true","True"}:
            clear_plan_state()
    except Exception:
        pass


class StepIn(BaseModel):
    type: str = Field(default="task", description="step type, e.g., task|job|api")
    payload: Dict[str, Any] = Field(default_factory=dict)

class PlanIn(BaseModel):
    title: str = ""
    steps: List[StepIn] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


def _now() -> int: return int(time.time())


def _plan_to_dict(p: Plan, steps: Optional[List[PlanStep]] = None) -> Dict[str, Any]:
    return {
        "id": int(p.id),
        "title": p.title or "",
        "user_id": int(p.user_id or 0),
        "status": p.status or "queued",
        "meta": json.loads(p.meta or "{}") if isinstance(p.meta, str) else (p.meta or {}),
        "created_at": int(p.created_at or 0),
        "updated_at": int(p.updated_at or 0),
        "started_at": int(p.started_at or 0),
        "finished_at": int(p.finished_at or 0),
        "steps": [
            {
                "id": int(s.id),
                "plan_id": int(s.plan_id or 0),
                "idx": int(s.idx or 0),
                "type": s.type or "",
                "payload": json.loads(s.payload or "{}") if isinstance(s.payload, str) else (s.payload or {}),
                "status": s.status or "queued",
                "result": s.result or "",
                "error": s.error or "",
                "created_at": int(s.created_at or 0),
                "updated_at": int(s.updated_at or 0),
                "started_at": int(s.started_at or 0),
                "finished_at": int(s.finished_at or 0),
            }
            for s in (steps if steps is not None else [])
        ] if steps is not None else None,
    }


@router.post("")
def create_plan(body: PlanIn, user = Depends(get_current_user_required)):
    # Only creator/admin can create plans
    require_role(user, {"creator", "admin"})
    now = _now()
    with SessionLocal() as db:
        p = Plan(
            title=(body.title or "").strip()[:200],
            user_id=int(user.get("id") or 0),
            status="queued",
            meta=json.dumps(body.meta or {}, ensure_ascii=False),
            created_at=now,
            updated_at=now,
            started_at=0,
            finished_at=0,
        )
        db.add(p); db.flush()
        for i, st in enumerate(body.steps or []):
            s = PlanStep(
                plan_id=int(p.id),
                idx=int(i),
                type=(st.type or "task")[:64],
                payload=json.dumps(st.payload or {}, ensure_ascii=False),
                status="queued",
                created_at=now,
                updated_at=now,
            )
            db.add(s)
        db.commit(); db.refresh(p)
        try:
            write_audit("plan_create", actor_id=int(user.get("id") or 0), target_type="plan", target_id=int(p.id or 0), meta={"title": p.title, "steps": len(body.steps or [])})
        except Exception:
            pass
        return {"ok": True, "plan": _plan_to_dict(p)}


@router.get("")
def list_plans(limit: int = 50, offset: int = 0, status: Optional[str] = None, user = Depends(get_current_user_required)):
    require_role(user, {"creator", "admin"})
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    with SessionLocal() as db:
        qry = db.query(Plan)
        if status:
            qry = qry.filter(Plan.status == status)
        rows = qry.order_by(Plan.created_at.desc()).offset(offset).limit(limit + 1).all()
        has_more = len(rows) > limit
        items = rows[:limit]
        return {"ok": True, "items": [_plan_to_dict(p) for p in items], "limit": limit, "offset": offset, "has_more": has_more}

@router.get("/count")
def count_plans(user = Depends(get_current_user_required)):
    require_role(user, {"creator", "admin"})
    with SessionLocal() as db:
        total = int(db.query(Plan).count() or 0)
        by_status = {}
        for st in ("queued","running","done","failed","canceled"):
            try:
                by_status[st] = int(db.query(Plan).filter(Plan.status == st).count() or 0)
            except Exception:
                by_status[st] = 0
        return {"ok": True, "total": total, "by_status": by_status}


@router.get("/{plan_id}")
def get_plan(plan_id: int, user = Depends(get_current_user_required)):
    require_role(user, {"creator", "admin"})
    with SessionLocal() as db:
        p = db.query(Plan).filter(Plan.id == int(plan_id)).first()
        if not p: raise HTTPException(404, "plan_not_found")
        steps = db.query(PlanStep).filter(PlanStep.plan_id == int(plan_id)).order_by(PlanStep.idx.asc(), PlanStep.id.asc()).all()
        return {"ok": True, "plan": _plan_to_dict(p, steps)}


@router.post("/{plan_id}/duplicate")
def duplicate_plan(plan_id: int, user = Depends(get_current_user_required)):
    require_role(user, {"creator", "admin"})
    now = int(time.time())
    with SessionLocal() as db:
        p = db.query(Plan).filter(Plan.id == int(plan_id)).first()
        if not p:
            raise HTTPException(404, "plan_not_found")
        steps = db.query(PlanStep).filter(PlanStep.plan_id == int(plan_id)).order_by(PlanStep.idx.asc(), PlanStep.id.asc()).all()
        title = (p.title or "").strip()
        new_title = (title + " (copy)")[:200]
        np = Plan(
            title=new_title,
            user_id=int(user.get("id") or 0),
            status="queued",
            meta=p.meta or "{}",
            created_at=now,
            updated_at=now,
            started_at=0,
            finished_at=0,
        )
        db.add(np); db.commit(); db.refresh(np)
        for s in steps:
            ns = PlanStep(
                plan_id=int(np.id or 0),
                idx=int(s.idx or 0),
                type=s.type or "task",
                payload=s.payload or "{}",
                status="queued",
                result="",
                error="",
                created_at=now,
                updated_at=now,
                started_at=0,
                finished_at=0,
            )
            db.add(ns)
        db.commit(); db.refresh(np)
        try:
            write_audit("plan_duplicate", actor_id=int(user.get("id") or 0), target_type="plan", target_id=int(np.id or 0), meta={"from": int(plan_id), "steps": len(steps)})
        except Exception:
            pass
        return {"ok": True, "plan": _plan_to_dict(np)}


@router.post("/{plan_id}/cancel")
def cancel_plan(plan_id: int, user = Depends(get_current_user_required)):
    require_role(user, {"creator", "admin"})
    with SessionLocal() as db:
        p = db.query(Plan).filter(Plan.id == int(plan_id)).first()
        if not p: raise HTTPException(404, "plan_not_found")
        if p.status in {"done", "failed", "canceled"}:
            return {"ok": True, "status": p.status}
        now = _now()
        p.status = "canceled"; p.updated_at = now; p.finished_at = now
        # cancel queued/running steps
        for s in db.query(PlanStep).filter(PlanStep.plan_id == int(plan_id)).all():
            if s.status in {"queued", "running"}:
                s.status = "canceled"; s.updated_at = now; s.finished_at = now
        db.add(p); db.commit()
        try:
            write_audit("plan_cancel", actor_id=int(user.get("id") or 0), target_type="plan", target_id=int(plan_id or 0))
        except Exception:
            pass
        # Reflection: if plan is now terminal, write a knowledge summary (best-effort)
        try:
            p2 = db.query(Plan).filter(Plan.id == int(body.plan_id)).first()
            if p2 and (p2.status in {"done", "failed", "canceled"}):
                steps_all = db.query(PlanStep).filter(PlanStep.plan_id == int(body.plan_id)).order_by(PlanStep.idx.asc(), PlanStep.id.asc()).all()
                total = len(steps_all)
                ok_n = sum(1 for x in steps_all if (x.status or "") == "done")
                fail_n = sum(1 for x in steps_all if (x.status or "") == "failed")
                # Small media summary snippet
                snips = []
                for x in steps_all:
                    xt = (x.type or "").lower()
                    if xt == "media_whisper" and (x.result or ""):
                        snips.append((x.result or "")[:160])
                content = f"Plan #{int(p2.id)} abgeschlossen: {total} Schritte, {ok_n} ok, {fail_n} Fehler. Status: {p2.status}.\n"
                if snips:
                    content += "Whisper-Zusammenfassung:\n- " + "\n- ".join(snips)
                # Post to knowledge
                try:
                    import requests as _rq
                    admin_tok = os.getenv("ADMIN_API_TOKEN", "").strip()
                    headers = {"Content-Type": "application/json"}
                    if admin_tok:
                        headers["Authorization"] = f"Bearer {admin_tok}"
                    base = os.getenv("PLANNER_API_BASE", "http://127.0.0.1:8000").rstrip("/")
                    _rq.post(base+"/api/knowledge", json={
                        "source": f"plan:{int(p2.id)}", "type": "reflection", "tags": "reflection,planner",
                        "content": content
                    }, headers=headers, timeout=2)
                except Exception:
                    pass
                # Also audit reflection
                try:
                    write_audit("plan_reflection", actor_id=int(user.get("id") or 0), target_type="plan", target_id=int(p2.id or 0), meta={"total": total, "ok": ok_n, "failed": fail_n, "status": p2.status})
                except Exception:
                    pass
        except Exception:
            pass
        return {"ok": True}


@router.post("/{plan_id}/retry")
def retry_plan(plan_id: int, user = Depends(get_current_user_required)):
    require_role(user, {"creator", "admin"})
    with SessionLocal() as db:
        p = db.query(Plan).filter(Plan.id == int(plan_id)).first()
        if not p: raise HTTPException(404, "plan_not_found")
        now = _now()
        # reset plan and all steps to queued
        p.status = "queued"; p.updated_at = now; p.started_at = 0; p.finished_at = 0
        for s in db.query(PlanStep).filter(PlanStep.plan_id == int(plan_id)).all():
            s.status = "queued"; s.updated_at = now; s.started_at = 0; s.finished_at = 0; s.result = ""; s.error = ""
        db.add(p); db.commit()
        try:
            write_audit("plan_retry", actor_id=int(user.get("id") or 0), target_type="plan", target_id=int(plan_id or 0))
        except Exception:
            pass
        return {"ok": True}


class LeaseIn(BaseModel):
    # Lease the next queued step for the earliest queued or running plan
    pass


@router.post("/lease-step")
def lease_step(body: LeaseIn, user = Depends(get_current_user_required)):
    # Allow worker/admin to lease
    require_role(user, {"admin", "worker", "creator"})
    now = _now()
    with SessionLocal() as db:
        # find the earliest plan with queued steps
        p = (
            db.query(Plan)
              .filter(Plan.status.in_(["queued", "running"]))
              .order_by(Plan.created_at.asc())
              .first()
        )
        if not p:
            return {"ok": True, "step": None}
        # find next queued step by idx
        s = (
            db.query(PlanStep)
              .filter(PlanStep.plan_id == int(p.id), PlanStep.status == "queued")
              .order_by(PlanStep.idx.asc(), PlanStep.id.asc())
              .first()
        )
        if not s:
            # no queued steps left → finalize plan if running/queued
            if p.status in {"queued", "running"}:
                p.status = "done"; p.finished_at = now; p.updated_at = now
                db.add(p); db.commit()
            return {"ok": True, "step": None}
        # mark plan running and lease step (best-effort lock)
        p.status = "running"; p.updated_at = now; p.started_at = p.started_at or now
        s.status = "running"; s.started_at = now; s.updated_at = now
        db.add(p); db.add(s); db.commit(); db.refresh(s)
        return {"ok": True, "step": _plan_to_dict(p, [s])["steps"][0], "plan_id": int(p.id)}


class CompleteIn(BaseModel):
    step_id: int
    plan_id: int
    ok: bool = True
    result: Optional[str] = None
    error: Optional[str] = None


@router.post("/complete-step")
def complete_step(body: CompleteIn, user = Depends(get_current_user_required)):
    require_role(user, {"admin", "worker", "creator"})
    now = _now()
    with SessionLocal() as db:
        s = db.query(PlanStep).filter(PlanStep.id == int(body.step_id), PlanStep.plan_id == int(body.plan_id)).first()
        if not s: raise HTTPException(404, "step_not_found")
        if s.status not in {"running", "queued"}:
            return {"ok": True, "status": s.status}
        s.status = "done" if bool(body.ok) else "failed"
        s.result = (body.result or "")[:2000]
        s.error = (body.error or "")[:2000]
        s.finished_at = now; s.updated_at = now
        db.add(s)
        # if failed, mark plan failed
        p = db.query(Plan).filter(Plan.id == int(body.plan_id)).first()
        if p:
            if not body.ok:
                p.status = "failed"; p.finished_at = now
            p.updated_at = now
            db.add(p)
        db.commit()
        # Audit specialized step completions (best-effort)
        try:
            stype = (s.type or "").lower()
            meta = {}
            try:
                payload = json.loads(s.payload or "{}") if isinstance(s.payload, str) else (s.payload or {})
            except Exception:
                payload = {}
            if stype == "device_event":
                dev_id = int((payload.get("device_id") or 0))
                ev = payload.get("event") or {}
                ev_type = str(ev.get("type") or "").strip()
                meta = {"device_id": dev_id, "event_type": ev_type, "ok": bool(body.ok)}
                write_audit("plan_device_event", actor_id=int(user.get("id") or 0), target_type="plan", target_id=int(body.plan_id or 0), meta=meta)
            elif stype == "knowledge_add":
                content_len = 0
                try:
                    content_len = len(str((payload.get("content") or "")))
                except Exception:
                    content_len = 0
                meta = {"content_len": int(content_len), "ok": bool(body.ok)}
                write_audit("plan_knowledge_add", actor_id=int(user.get("id") or 0), target_type="plan", target_id=int(body.plan_id or 0), meta=meta)
            elif stype == "media_thumbnail":
                p = str(payload.get("path") or "")
                mw = int(payload.get("max_w") or payload.get("w") or 0)
                mh = int(payload.get("max_h") or payload.get("h") or 0)
                meta = {"path": p, "w": mw, "h": mh, "ok": bool(body.ok)}
                write_audit("plan_media_thumbnail", actor_id=int(user.get("id") or 0), target_type="plan", target_id=int(body.plan_id or 0), meta=meta)
            elif stype == "media_whisper":
                p = str(payload.get("path") or "")
                lg = str(payload.get("lang") or "")
                meta = {"path": p, "lang": lg, "ok": bool(body.ok)}
                write_audit("plan_media_whisper", actor_id=int(user.get("id") or 0), target_type="plan", target_id=int(body.plan_id or 0), meta=meta)
        except Exception:
            pass
        return {"ok": True}
