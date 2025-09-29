from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
import time, json

from ...deps import get_current_user_required, get_db
from ...models import Job
try:
    from ..admin.router import write_audit  # type: ignore
except Exception:
    def write_audit(*args, **kwargs):  # type: ignore
        return None
from pathlib import Path
import json, os, time

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _now() -> int:
    return int(time.time())


def _require_admin_or_worker(user: dict) -> None:
    role = str(user.get("role") or "").lower()
    roles = set([role] + [str(r).lower() for r in (user.get("roles") or [])])
    # Allow admin, worker, creator, papa to access jobs API (used by Papa UI)
    if not ("admin" in roles or "worker" in roles or "creator" in roles or "papa" in roles):
        raise HTTPException(403, "admin/worker/creator/papa role required")

# In-memory heartbeat store: { key -> { name, type, status, ts, pid, job_types, host } }
HEARTBEATS: Dict[str, Dict[str, Any]] = {}

@router.post("/heartbeat")
def post_heartbeat(payload: Dict[str, Any], request: Request):
    """Accept lightweight heartbeat updates from local workers.

    Expected fields: name (str), type (str), status (str), pid (int), job_types (list[str])
    Security: allow only localhost to post without auth.
    """
    try:
        host = (request.client.host if request.client else "") or ""
    except Exception:
        host = ""
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "heartbeat posts must originate from localhost")
    name = str(payload.get("name") or payload.get("type") or "worker").strip() or "worker"
    rec: Dict[str, Any] = {
        "name": name,
        "type": str(payload.get("type") or "").strip() or None,
        "status": str(payload.get("status") or "ok").strip() or "ok",
        "ts": int(payload.get("ts") or _now()),
        "pid": int(payload.get("pid") or 0) or None,
        "job_types": payload.get("job_types") if isinstance(payload.get("job_types"), list) else None,
        "host": host,
    }
    HEARTBEATS[name] = rec
    return {"ok": True}


@router.post("/enqueue")
def enqueue(payload: Dict[str, Any], user = Depends(get_current_user_required), db: Session = Depends(get_db)):
    _require_admin_or_worker(user)
    jtype = str(payload.get("type") or "").strip()
    if not jtype:
        raise HTTPException(400, "type required")
    content = payload.get("payload") or {}
    if not isinstance(content, dict):
        raise HTTPException(400, "payload must be object")
    idem = payload.get("idempotency_key")
    if idem:
        # Return existing job if same idempotency key
        existing = db.query(Job).filter(Job.idempotency_key == str(idem)).first()
        if existing:
            return {"ok": True, "id": existing.id, "status": existing.status}
    j = Job(
        type=jtype,
        payload=json.dumps(content, ensure_ascii=False),
        status="queued",
        attempts=0,
        lease_until=0,
        idempotency_key=str(idem) if idem else None,
        priority=int(payload.get("priority") or 0),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(j); db.commit(); db.refresh(j)
    return {"ok": True, "id": j.id}


class LeaseIn(dict):
    pass


@router.post("/lease")
def lease(body: LeaseIn, user = Depends(get_current_user_required), db: Session = Depends(get_db)):
    _require_admin_or_worker(user)
    jtype = str(body.get("type") or "").strip()
    n = int(body.get("n") or 1)
    lease_seconds = int(body.get("lease_seconds") or 60)
    now = _now()
    # Select queued or expired leases, highest priority first, FIFO by id
    jobs = (
        db.query(Job)
        .filter(Job.type == jtype, ((Job.status == "queued") | (Job.lease_until < now)))
        .order_by(Job.priority.desc(), Job.id.asc())
        .limit(max(1, n))
        .all()
    )
    out: List[Dict[str, Any]] = []
    for j in jobs:
        j.status = "leased"
        j.lease_until = now + lease_seconds
        j.updated_at = now
        db.add(j)
        out.append({
            "id": j.id,
            "type": j.type,
            "payload": json.loads(j.payload or "{}"),
            "attempts": j.attempts,
            "lease_until": j.lease_until,
            "priority": j.priority,
        })
    db.commit()
    return {"ok": True, "items": out}


@router.post("/done")
def done(body: Dict[str, Any], user = Depends(get_current_user_required), db: Session = Depends(get_db)):
    _require_admin_or_worker(user)
    jid = int(body.get("id") or 0)
    if not jid:
        raise HTTPException(400, "id required")
    j = db.query(Job).filter(Job.id == jid).first()
    if not j:
        raise HTTPException(404, "job not found")
    j.status = "done"
    j.lease_until = 0
    j.updated_at = _now()
    db.add(j); db.commit()
    return {"ok": True}


@router.post("/fail")
def fail(body: Dict[str, Any], user = Depends(get_current_user_required), db: Session = Depends(get_db)):
    _require_admin_or_worker(user)
    jid = int(body.get("id") or 0)
    err = str(body.get("error") or "")
    next_delay = int(body.get("next_delay") or 0)
    max_attempts = int(body.get("max_attempts") or 5)
    if not jid:
        raise HTTPException(400, "id required")
    j = db.query(Job).filter(Job.id == jid).first()
    if not j:
        raise HTTPException(404, "job not found")
    j.attempts = int(j.attempts or 0) + 1
    j.error = err[:2000]
    now = _now()
    if j.attempts >= max_attempts:
        j.status = "failed"
        j.lease_until = 0
    else:
        j.status = "queued"
        # exponential-ish backoff if not provided
        if next_delay <= 0:
            next_delay = min(3600, 5 * (2 ** min(6, j.attempts)))
        j.lease_until = now + next_delay
    j.updated_at = now
    db.add(j); db.commit()
    return {"ok": True, "status": j.status, "attempts": j.attempts}


@router.get("/status")
def status(user = Depends(get_current_user_required), db: Session = Depends(get_db)):
    _require_admin_or_worker(user)
    # quick counts by status
    from sqlalchemy import func
    rows = db.query(Job.status, func.count(Job.id)).group_by(Job.status).all()
    by_status = {s or "": int(c) for s, c in rows}
    rows2 = db.query(Job.type, func.count(Job.id)).group_by(Job.type).all()
    by_type = {t or "": int(c) for t, c in rows2}
    return {"ok": True, "by_status": by_status, "by_type": by_type}


@router.get("")
def list_jobs(limit: int = 50, user = Depends(get_current_user_required), db: Session = Depends(get_db)):
    _require_admin_or_worker(user)
    limit = max(1, min(200, int(limit)))
    rows = (
        db.query(Job)
        .order_by(Job.id.desc())
        .limit(limit)
        .all()
    )
    items: List[Dict[str, Any]] = []
    for j in rows:
        try:
            items.append({
                "id": j.id,
                "type": j.type,
                "status": j.status,
                "attempts": j.attempts,
                "lease_until": j.lease_until,
                "priority": j.priority,
                "error": j.error,
                "payload": json.loads(j.payload or "{}"),
                "created_at": j.created_at,
                "updated_at": j.updated_at,
            })
        except Exception:
            continue
    return {"ok": True, "items": items}


@router.post("/retry-failed")
def retry_failed(max_attempts: int = 5, user = Depends(get_current_user_required), db: Session = Depends(get_db)):
    """Requeue all failed jobs that haven't exceeded max_attempts.

    Sets status=queued and clears lease. Returns count of requeued jobs.
    """
    _require_admin_or_worker(user)
    rows = (
        db.query(Job)
        .filter(Job.status == "failed", Job.attempts < int(max_attempts or 5))
        .all()
    )
    now = _now()
    cnt = 0
    for j in rows:
        j.status = "queued"; j.lease_until = 0; j.updated_at = now
        db.add(j); cnt += 1
    db.commit()
    # Audit
    try:
        write_audit(
            "jobs_retry_failed",
            actor_id=int(user.get("id") or 0),
            target_type="jobs",
            target_id=0,
            meta={"requeued": int(cnt), "max_attempts": int(max_attempts or 5)},
        )
    except Exception:
        pass
    return {"ok": True, "requeued": cnt}


@router.post("/purge")
def purge(status: str = "done", older_than_seconds: int = 86400, limit: int = 500, user = Depends(get_current_user_required), db: Session = Depends(get_db)):
    """Delete jobs by status older than a given age (default 1 day).

    status: done|failed|any
    """
    _require_admin_or_worker(user)
    status = (status or "done").lower().strip()
    older = max(0, int(older_than_seconds or 0))
    lim = max(1, min(5000, int(limit or 500)))
    now = _now()
    q = db.query(Job)
    if status != "any":
        q = q.filter(Job.status == status)
    q = q.filter(Job.updated_at <= (now - older)).order_by(Job.id.asc()).limit(lim)
    rows = q.all()
    cnt = 0
    for j in rows:
        db.delete(j); cnt += 1
    db.commit()
    try:
        write_audit(
            "jobs_purge",
            actor_id=int(user.get("id") or 0),
            target_type="jobs",
            target_id=0,
            meta={
                "deleted": int(cnt),
                "status": status,
                "older_than_seconds": int(older),
                "limit": int(lim),
            },
        )
    except Exception:
        pass
    return {"ok": True, "deleted": cnt}


@router.get("/heartbeats")
def heartbeats(user = Depends(get_current_user_required)):
    """Return worker heartbeat snapshots found in KI_ROOT/logs.

    Shape: { ok:true, items: [ {name, ts, age, host, pid, job_types, last_* }, ... ] }
    """
    _require_admin_or_worker(user)
    root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
    logdir = root / "logs"
    items: List[Dict[str, Any]] = []
    now = int(time.time())

    # 1) File-based heartbeats (backward compatible)
    try:
        for p in logdir.glob("worker_heartbeat_*.json"):
            try:
                j = json.loads(p.read_text(encoding='utf-8'))
                if not isinstance(j, dict):
                    continue
                rec = dict(j)
                ts = int(rec.get('ts') or 0)
                rec['age'] = max(0, now - ts)
                rec['file'] = p.name
                items.append(rec)
            except Exception:
                continue
    except Exception:
        pass

    # 2) In-memory heartbeats from POST /heartbeat
    try:
        for rec in HEARTBEATS.values():
            r = dict(rec)
            ts = int(r.get('ts') or 0)
            r['age'] = max(0, now - ts)
            items.append(r)
    except Exception:
        pass

    # Sort by name for stable display
    items.sort(key=lambda x: str(x.get('name') or ''))
    return {"ok": True, "items": items}
