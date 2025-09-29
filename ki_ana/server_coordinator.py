import os, time, json, hmac, hashlib, base64
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException, Body, Header, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from .db import SessionLocal, create_all
from .models import Job, Node, Artifact
from storage_minio import presign_get as minio_presign_get, presign_put as minio_presign_put
from dotenv import load_dotenv

# Load environment from .env if present (MVP convenience)
load_dotenv()

LEASE_SECONDS = int(os.getenv("LEASE_SECONDS", "600"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
JWT_SECRET = os.getenv("JWT_SECRET", "")

app = FastAPI(title="Coordinator", version="0.3.0")
create_all()  # auto-create tables for MVP


def now() -> float:
    return time.time()


def require_role(authorization: Optional[str], roles=("worker", "admin")) -> str:
    if not JWT_SECRET:
        return "public"
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        h_b64, p_b64, s_b64 = token.split(".")
        signing_input = (h_b64 + "." + p_b64).encode()
        expected = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
        pad = '=' * (-len(s_b64) % 4)
        sig = base64.urlsafe_b64decode(s_b64 + pad)
        if not hmac.compare_digest(expected, sig):
            raise HTTPException(401, "bad token")
        padp = '=' * (-len(p_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(p_b64 + padp))
        role = payload.get("role")
        if role not in roles:
            raise HTTPException(403, "insufficient role")
        return role
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "invalid token")


@app.get("/api/nodes/hello")
def hello():
    with SessionLocal() as s:
        pending = s.query(Job).filter(Job.status == "pending").count()
        assigned = s.query(Job).filter(Job.status == "assigned").count()
        done = s.query(Job).filter(Job.status == "done").count()
        failed = s.query(Job).filter(Job.status == "failed").count()
    return {"ok": True, "time": now(), "jobs_pending": pending, "jobs_assigned": assigned, "jobs_done": done, "jobs_failed": failed}


@app.post("/api/jobs/submit")
def submit_job(job: Dict[str, Any] = Body(...), authorization: Optional[str] = Header(default=None)):
    require_role(authorization, ("admin",))
    if not {"type", "cid"}.issubset(job.keys()):
        raise HTTPException(400, "need type,cid")
    job_id = hashlib.sha256((json.dumps(job, sort_keys=True) + str(now())).encode()).hexdigest()[:16]
    with SessionLocal() as s:
        j = Job(
            id=job_id,
            type=job["type"],
            cid=job["cid"],
            params_json=json.dumps(job.get("params") or {}),
            status="pending",
            retries=0,
            lease_until=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        s.add(j)
        s.commit()
    return {"ok": True, "job_id": job_id}


def select_next_job(s: Session) -> Optional[Job]:
    t = now()
    q = (
        s.query(Job)
        .filter(
            or_(
                Job.status == "pending",
                and_(Job.status == "assigned", Job.lease_until != None, Job.lease_until < t),  # noqa: E711
            ),
            Job.retries < MAX_RETRIES,
        )
        .order_by(Job.created_at.asc())
        .limit(1)
    )
    return q.one_or_none()


@app.get("/api/jobs/next")
def jobs_next(authorization: Optional[str] = Header(default=None), x_worker_id: Optional[str] = Header(default=None)):
    require_role(authorization, ("worker",))
    worker_id = x_worker_id or "unknown"
    with SessionLocal() as s:
        node = s.get(Node, worker_id)
        if not node:
            node = Node(id=worker_id, caps="", last_seen=now())
            s.add(node)
        else:
            node.last_seen = now()

        job = select_next_job(s)
        if not job:
            s.commit()
            return JSONResponse(status_code=204, content=None)

        job.status = "assigned"
        job.retries = job.retries + 1
        job.assigned_node = worker_id
        job.lease_until = now() + LEASE_SECONDS
        job.updated_at = datetime.utcnow()
        s.commit()

        ticket = {"id": job.id, "type": job.type, "cid": job.cid, "issued_at": now()}
        try:
            artifact_url = minio_presign_get(job.cid, ttl_seconds=min(600, LEASE_SECONDS))
        except Exception as e:
            raise HTTPException(500, f"presign_get failed: {e}")
        return {"ticket": ticket, "artifact_url": artifact_url}


@app.post("/api/artifacts/presign_put")
def artifacts_presign_put(job_id: str, cid: str, authorization: Optional[str] = Header(default=None), x_worker_id: Optional[str] = Header(default=None)):
    require_role(authorization, ("worker", "admin"))
    with SessionLocal() as s:
        job = s.get(Job, job_id)
        if not job:
            raise HTTPException(404, "unknown job")
    url = minio_presign_put(cid, ttl_seconds=600)
    return {"put_url": url, "expires_in": 600}


@app.post("/api/jobs/{job_id}/result")
def job_result(job_id: str, body: Dict[str, Any] = Body(...), authorization: Optional[str] = Header(default=None), x_worker_id: Optional[str] = Header(default=None)):
    require_role(authorization, ("worker", "admin"))
    with SessionLocal() as s:
        job = s.get(Job, job_id)
        if not job:
            raise HTTPException(404, "unknown job")
        status = body.get("status", "ok")
        result_cid = body.get("result_cid")
        job.status = "done" if status == "ok" else "failed"
        job.assigned_node = x_worker_id or body.get("worker_id")
        job.lease_until = None
        job.updated_at = datetime.utcnow()
        if result_cid:
            a = Artifact(job_id=job.id, cid=result_cid, kind="result", storage_backend="minio", created_at=datetime.utcnow())
            s.add(a)
        s.commit()
    return {"ok": True}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    with SessionLocal() as s:
        pending = s.query(Job).filter(Job.status == "pending").count()
        assigned = s.query(Job).filter(Job.status == "assigned").count()
        done = s.query(Job).filter(Job.status == "done").count()
        failed = s.query(Job).filter(Job.status == "failed").count()
    lines = [
        "# HELP jobs_pending Number of pending jobs",
        "# TYPE jobs_pending gauge",
        f"jobs_pending {pending}",
        "# HELP jobs_assigned Number of assigned jobs",
        "# TYPE jobs_assigned gauge",
        f"jobs_assigned {assigned}",
        "# HELP jobs_done Number of done jobs",
        "# TYPE jobs_done counter",
        f"jobs_done {done}",
        "# HELP jobs_failed Number of failed jobs",
        "# TYPE jobs_failed counter",
        f"jobs_failed {failed}",
    ]
    return "\n".join(lines)


@app.get("/")
def root():
    return {"name": "Coordinator", "version": "0.3.0"}
