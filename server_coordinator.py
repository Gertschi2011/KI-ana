from __future__ import annotations
import os, json, time, datetime as dt
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session

from minio import Minio

# Projektmodule
from .db import SessionLocal
from .models import Job, Node, Artifact

# ENV laden
load_dotenv()

# --- Konfiguration ---
LEASE_SECONDS = int(os.getenv("LEASE_SECONDS", "600"))
MAX_RETRIES   = int(os.getenv("MAX_RETRIES", "3"))
JWT_SECRET    = os.getenv("JWT_SECRET")

MINIO_ENDPOINT    = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY  = os.getenv("MINIO_ACCESS_KEY", "minio")
MINIO_SECRET_KEY  = os.getenv("MINIO_SECRET_KEY", "minio123")
MINIO_BUCKET      = os.getenv("MINIO_BUCKET", "artifacts")
MINIO_SECURE      = os.getenv("MINIO_SECURE", "false").lower() == "true"

_minio = Minio(MINIO_ENDPOINT,
               access_key=MINIO_ACCESS_KEY,
               secret_key=MINIO_SECRET_KEY,
               secure=MINIO_SECURE)
try:
    if not _minio.bucket_exists(MINIO_BUCKET):
        _minio.make_bucket(MINIO_BUCKET)
except Exception:
    pass

# --- Helpers ---
def presign_get(cid_hex: str, ttl: int = LEASE_SECONDS) -> str:
    from datetime import timedelta
    return _minio.get_presigned_url("GET", MINIO_BUCKET, f"artifacts/{cid_hex}",
                                    expires=timedelta(seconds=ttl))

def presign_put(cid_hex: str, ttl: int = LEASE_SECONDS) -> str:
    from datetime import timedelta
    return _minio.get_presigned_url("PUT", MINIO_BUCKET, f"artifacts/{cid_hex}",
                                    expires=timedelta(seconds=ttl))

def require_role(required: Optional[str] = None):
    def _dep(authorization: Optional[str] = Header(default=None)) -> None:
        if not JWT_SECRET:
            return
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "missing bearer token")
        token = authorization.split(" ", 1)[1]
        # TODO: hier echtes JWT-Verify einbauen
        if required == "admin" and ".admin." not in f".{token}.":
            raise HTTPException(403, "admin required")
    return _dep

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- FastAPI ---
app = FastAPI(title="KI_ana Coordinator", version="0.1")

# --- Schemas ---
class JobIn(BaseModel):
    type: str
    cid: str
    params: dict | None = None

class JobTicket(BaseModel):
    job_id: str
    type: str
    artifact_url: str
    cid: str
    params: dict

class JobResultIn(BaseModel):
    job_id: str
    worker_id: str
    status: str
    result_cid: Optional[str] = None
    metrics: Optional[dict] = None
    log_tail: Optional[str] = None

class NodePing(BaseModel):
    worker_id: str
    caps: Optional[dict] = None
    version: Optional[str] = None

# --- Node-Routen ---
@app.get("/api/nodes/hello")
def nodes_hello():
    return {"status": "ok", "ts": int(time.time() * 1000)}

@app.post("/api/nodes/ping")
def nodes_ping(ping: NodePing, db: Session = Depends(get_db)):
    now = time.time()
    node = db.get(Node, ping.worker_id)
    if node:
        node.caps = json.dumps(ping.caps or {})
        node.last_seen = now
    else:
        node = Node(id=ping.worker_id,
                    caps=json.dumps(ping.caps or {}),
                    last_seen=now)
        db.add(node)
    db.commit()
    return {"ok": True, "ts": int(now * 1000)}

# --- Job-Routen ---
@app.post("/api/jobs/submit")
def submit_job(job: JobIn, _: None = Depends(require_role("admin")), db: Session = Depends(get_db)):
    now = dt.datetime.utcnow()
    j = Job(type=job.type,
            cid=job.cid,
            params_json=json.dumps(job.params or {}),
            status="pending",
            assigned_node=None,
            lease_until=None,
            retries=0,
            created_at=now,
            updated_at=now)
    db.add(j); db.flush()
    db.add(Artifact(job_id=j.id, cid=job.cid, kind="input",
                    storage_backend="minio", created_at=now))
    db.commit()
    return {"job_id": str(j.id)}

@app.get("/api/jobs/next")
def next_job(worker_id: Optional[str] = None, db: Session = Depends(get_db)) -> dict:
    now = dt.datetime.utcnow()
    q = (select(Job)
         .where(
             or_(
                 Job.status == "pending",
                 and_(Job.status == "assigned",
                      Job.lease_until != None,
                      Job.lease_until < now),
             ),
             Job.retries < MAX_RETRIES,
         )
         .order_by(Job.created_at.asc())
         .limit(1))
    j = db.scalars(q).first()
    if not j:
        raise HTTPException(204, "no jobs")
    j.status = "assigned"
    j.assigned_node = worker_id or "unknown"
    j.lease_until = now + dt.timedelta(seconds=LEASE_SECONDS)
    j.retries = (j.retries or 0) + 1
    j.updated_at = now
    db.commit(); db.refresh(j)
    url = presign_get(j.cid, ttl=LEASE_SECONDS)
    ticket = JobTicket(job_id=str(j.id),
                       type=j.type,
                       artifact_url=url,
                       cid=j.cid,
                       params=json.loads(j.params_json or "{}"))
    return {"ticket": ticket.model_dump()}

@app.post("/api/artifacts/presign_put")
def artifact_presign_put(job_id: str, cid: str, ttl: int = LEASE_SECONDS):
    return {"put_url": presign_put(cid, ttl=ttl)}

@app.post("/api/jobs/{job_id}/result")
def post_result(job_id: str, r: JobResultIn, db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(404, "unknown job")
    now = dt.datetime.utcnow()
    if r.status == "ok":
        j.status = "done"
    else:
        if (j.retries or 0) < MAX_RETRIES:
            j.status = "pending"
            j.assigned_node = None
            j.lease_until = None
        else:
            j.status = "failed"
    j.updated_at = now
    db.add(j)
    if r.result_cid:
        db.add(Artifact(job_id=j.id, cid=r.result_cid, kind="result",
                        storage_backend="minio", created_at=now))
    db.commit()
    return {"ok": True}

# --- Metrics ---
@app.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            func.sum(func.case((Job.status == "pending", 1), else_=0)).label("pending"),
            func.sum(func.case((Job.status == "assigned", 1), else_=0)).label("assigned"),
            func.sum(func.case((Job.status == "done", 1), else_=0)).label("done"),
            func.sum(func.case((Job.status == "failed", 1), else_=0)).label("failed"),
        )
    ).first()
    pending, assigned, done, failed = [int(x or 0) for x in rows]
    text = (
        f"# HELP jobs_pending gauge\njobs_pending {pending}\n"
        f"# HELP jobs_assigned gauge\njobs_assigned {assigned}\n"
        f"# HELP jobs_done counter\njobs_done {done}\n"
        f"# HELP jobs_failed counter\njobs_failed {failed}\n"
    )
    return PlainTextResponse(text)