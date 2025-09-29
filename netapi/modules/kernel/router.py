# netapi/modules/kernel/router.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, validator
from typing import Dict, Any, Optional

from .core import KERNEL
from .scheduler import SCHED
from netapi.deps import get_current_user_required

router = APIRouter(prefix="/kernel", tags=["kernel"])  # final mount adds /api


# -----------------------------
# Models
# -----------------------------
class ExecIn(BaseModel):
    skill: str
    action: str
    args: Dict[str, Any] = {}


class JobIn(BaseModel):
    skill: str
    action: str
    args: Dict[str, Any] = {}
    enabled: bool = True
    schedule: Dict[str, Any]

    @validator("schedule")
    def _validate_schedule(cls, v: Dict[str, Any]):
        if not isinstance(v, dict):
            raise ValueError("schedule must be an object")
        if not any(k in v for k in ("every_seconds", "cron")):
            raise ValueError("schedule requires 'every_seconds' or 'cron'")
        if "every_seconds" in v:
            try:
                iv = int(v["every_seconds"])  # raises if not int-like
                if iv <= 0:
                    raise ValueError
            except Exception:
                raise ValueError("every_seconds must be positive integer")
        if "cron" in v:
            if not isinstance(v["cron"], str) or not v["cron"].strip():
                raise ValueError("cron must be a non-empty string")
        return v


# -----------------------------
# Kernel status / inventory
# -----------------------------
@router.get("/status")
async def status():
    return {
        "running": True,
        "skills": [
            {
                "name": s.name,
                "version": s.version,
                "caps": s.capabilities,
                "schedule_every": s.schedule_every,
                "run_mode": s.run_mode,
            }
            for s in KERNEL.skills.values()
        ],
        "jobs": SCHED.list(),
    }


@router.get("/skills")
async def list_skills():
    """Lightweight manifest view for the Skill Registry UI."""
    items = []
    for spec in KERNEL.skills.values():
        items.append({
            "name": spec.name,
            "version": spec.version,
            "entrypoint": spec.entrypoint,
            "capabilities": spec.capabilities,
            "run_mode": spec.run_mode,
            "schedule_every": spec.schedule_every,
        })
    return {"count": len(items), "items": items}


@router.get("/skills/{name}")
async def get_skill(name: str):
    spec = KERNEL.skills.get(name)
    if not spec:
        raise HTTPException(status_code=404, detail="skill_not_found")
    return {
        "name": spec.name,
        "version": spec.version,
        "entrypoint": spec.entrypoint,
        "capabilities": spec.capabilities,
        "run_mode": spec.run_mode,
        "schedule_every": spec.schedule_every,
    }


# -----------------------------
# Lifecycle
# -----------------------------
@router.post("/reload")
async def reload_kernel(user = Depends(get_current_user_required)):
    role = (user.get("role") or "user").lower()
    if role not in ("creator", "admin"):
        raise HTTPException(403, "admin/creator required")
    await KERNEL.reload()
    return {"ok": True}


# -----------------------------
# Exec API
# -----------------------------
@router.post("/exec")
async def exec_skill(body: ExecIn, user = Depends(get_current_user_required)):
    role = (user.get("role") or "user").lower()
    res = await KERNEL.exec(body.skill, body.action, body.args, role=role)
    if not res.get("ok"):
        # bubble up error code as detail
        raise HTTPException(400, res.get("error", "exec_failed"))
    return res


# -----------------------------
# Jobs API
# -----------------------------
@router.get("/jobs")
async def list_jobs(user = Depends(get_current_user_required)):
    return {"items": SCHED.list()}


@router.post("/jobs")
async def add_job(body: JobIn, user = Depends(get_current_user_required)):
    role = (user.get("role") or "user").lower()
    if role not in ("creator", "admin"):
        raise HTTPException(403, "admin/creator required")
    job = SCHED.add(body.dict())
    return {"ok": True, "job": job}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, user = Depends(get_current_user_required)):
    role = (user.get("role") or "user").lower()
    if role not in ("creator", "admin"):
        raise HTTPException(403, "admin/creator required")
    ok = SCHED.delete(job_id)
    if not ok:
        raise HTTPException(404, "job not found")
    return {"ok": True}


@router.post("/jobs/{job_id}/toggle")
async def toggle_job(job_id: str, enabled: bool = True, user = Depends(get_current_user_required)):
    role = (user.get("role") or "user").lower()
    if role not in ("creator", "admin"):
        raise HTTPException(403, "admin/creator required")
    job = SCHED.toggle(job_id, enabled)
    if not job:
        raise HTTPException(404, "job not found")
    return {"ok": True, "job": job}


# NOTE:
# - Kernel start/stop is handled centrally in app startup/shutdown.
# - This router only exposes control & registry endpoints.
