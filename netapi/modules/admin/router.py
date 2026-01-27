from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict
from pydantic import BaseModel
import json, time
from werkzeug.security import generate_password_hash

from ...deps import get_current_user_required, require_role
from ...db import SessionLocal
from ...models import AdminAudit, User

router = APIRouter(prefix="/api/admin", tags=["admin"])


def write_audit(action: str, *, actor_id: int, target_type: str, target_id: int = 0, meta: Dict[str, Any] | None = None) -> None:
    try:
        with SessionLocal() as db:
            now = int(time.time())
            aa = AdminAudit(
                ts=now,
                actor_user_id=int(actor_id or 0),
                action=str(action)[:64],
                target_type=str(target_type)[:64],
                target_id=int(target_id or 0),
                meta=json.dumps(meta or {}, ensure_ascii=False)[:4000],
            )
            db.add(aa); db.commit()
    except Exception:
        # do not break main flow on audit errors
        pass


@router.get("/audit")
def list_audit(limit: int = 50, q: str = "", action: str = "", user = Depends(get_current_user_required)):
    require_role(user, {"creator"})
    try:
        limit = max(1, min(200, int(limit or 50)))
        with SessionLocal() as db:
            qy = db.query(AdminAudit)
            if action:
                qy = qy.filter(AdminAudit.action == str(action))
            rows = qy.order_by(AdminAudit.id.desc()).limit(limit).all()
            items = []
            ql = (q or "").lower().strip()
            for r in rows:
                try:
                    meta = {}
                    try:
                        meta = json.loads(r.meta or "{}")
                    except Exception:
                        meta = {"raw": (r.meta or "")[:200]}
                    rec = {
                        "ts": int(r.ts or 0),
                        "actor_user_id": int(r.actor_user_id or 0),
                        "action": r.action or "",
                        "target_type": r.target_type or "",
                        "target_id": int(r.target_id or 0),
                        "meta": meta,
                    }
                    if ql:
                        hay = (rec["action"] + " " + rec["target_type"] + " " + json.dumps(meta)).lower()
                        if ql not in hay:
                            continue
                    items.append(rec)
                except Exception:
                    continue
            return {"ok": True, "items": items}
    except Exception:
        return {"ok": True, "items": []}


@router.post("/plan-enforcer/run")
def run_plan_enforcer(user = Depends(get_current_user_required)):
    """Creator-only: run the plan enforcer now (auto-suspend expired plans)."""
    require_role(user, {"creator"})
    try:
        try:
            from system.plan_enforcer import enforce  # type: ignore
        except Exception:
            return {"ok": False, "error": "plan_enforcer_not_available"}
        n = int(enforce(dry_run=False) or 0)
        # Audit (actor 0 means system, here we log the trigger too)
        write_audit("plan_enforcer_run", actor_id=int(user.get("id") or 0), target_type="system", target_id=0, meta={"suspended": n})
        return {"ok": True, "suspended": n}
    except Exception:
        return {"ok": False, "error": "plan_enforcer_failed"}


# ========== USER MANAGEMENT ==========

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "user"
    is_papa: bool = False
    plan: str = "free"
    status: str = "active"  # active|locked


class UserUpdate(BaseModel):
    username: str | None = None
    email: str | None = None
    role: str | None = None
    is_papa: bool | None = None
    plan: str | None = None
    status: str | None = None  # active|locked


def _normalize_role(role: str | None) -> str:
    r = str(role or "user").strip().lower()
    if r in {"user", "user_pro"}:
        return r
    raise HTTPException(status_code=400, detail="role must be one of user|user_pro")


def _normalize_status_to_db(status: str | None) -> tuple[str, str]:
    """Return (account_status, reason_placeholder).

    UI contract uses active|locked. DB uses account_status + locked_until/is_active.
    Second tuple element kept for backward compatibility with existing call sites.
    """
    s = str(status or "active").strip().lower()
    if s in {"active", "unlock", "unlocked"}:
        return "active", ""
    if s in {"locked", "lock", "suspended"}:
        return "locked", ""
    raise HTTPException(status_code=400, detail="status must be one of active|locked")


def _status_for_ui(u: User) -> str:
    try:
        import time as _t
        now = int(_t.time())
    except Exception:
        now = 0
    try:
        if int(getattr(u, "deleted_at", 0) or 0) > 0:
            return "locked"
    except Exception:
        pass
    try:
        if int(getattr(u, "is_active", 1) or 1) == 0:
            return "locked"
    except Exception:
        pass
    try:
        if int(getattr(u, "locked_until", 0) or 0) > now:
            return "locked"
    except Exception:
        pass
    try:
        if str(getattr(u, "account_status", "active") or "active").strip().lower() != "active":
            return "locked"
    except Exception:
        pass
    return "active"


@router.get("/users")
def list_users(user = Depends(get_current_user_required)):
    """List all users (admin only)"""
    require_role(user, {"creator"})
    
    try:
        with SessionLocal() as db:
            users = db.query(User).all()
            return {
                "ok": True,
                "users": [
                    {
                        "id": u.id,
                        "username": u.username,
                        "email": u.email,
                        "role": u.role,
                        "roles": [u.role] if u.role else [],
                        "is_papa": u.is_papa,
                        "plan": u.plan,
                        "status": _status_for_ui(u),
                        "status_raw": getattr(u, 'account_status', None),
                        "deleted_at": int(getattr(u, 'deleted_at', 0) or 0),
                        "created_at": u.created_at,
                        "updated_at": u.updated_at
                    }
                    for u in users
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users")
def create_user(data: UserCreate, user = Depends(get_current_user_required)):
    """Create new user (admin only)"""
    require_role(user, {"creator"})
    
    try:
        with SessionLocal() as db:
            # Check if username/email exists
            existing = db.query(User).filter(
                (User.username == data.username) | (User.email == data.email)
            ).first()
            
            if existing:
                raise HTTPException(status_code=409, detail="Username or email already exists")

            role_norm = _normalize_role(data.role)
            acct_status, _reason_unused = _normalize_status_to_db(data.status)
            
            # Create user
            from datetime import datetime
            now = int(time.time())
            new_user = User(
                username=data.username,
                email=data.email,
                password_hash=generate_password_hash(data.password),
                role=role_norm,
                is_papa=data.is_papa,
                plan=data.plan,
                created_at=datetime.utcnow(),
                updated_at=now,
            )
            # lifecycle fields
            try:
                setattr(new_user, 'account_status', acct_status)
            except Exception:
                pass
            try:
                setattr(new_user, 'deleted_at', 0)
            except Exception:
                pass
            try:
                setattr(new_user, 'is_active', True if acct_status == 'active' else False)
            except Exception:
                pass
            try:
                # if locked, set a long lock window (UI still treats it as locked)
                setattr(new_user, 'locked_until', 0 if acct_status == 'active' else (now + 10 * 365 * 24 * 3600))
            except Exception:
                pass
            
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            # Audit
            write_audit("user_created", actor_id=int(user.get("id") or 0), target_type="user", target_id=new_user.id)
            
            return {"ok": True, "user_id": new_user.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/users/{user_id}")
def update_user(user_id: int, data: UserUpdate, user = Depends(get_current_user_required)):
    """Update user (admin only)"""
    require_role(user, {"creator"})
    
    try:
        with SessionLocal() as db:
            target_user = db.query(User).filter(User.id == user_id).first()
            
            if not target_user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Update fields
            from datetime import datetime
            if data.username is not None:
                # conflict check (exclude self)
                existing = db.query(User).filter(User.username == data.username, User.id != user_id).first()
                if existing:
                    raise HTTPException(status_code=409, detail="Username already exists")
                target_user.username = data.username
            if data.email is not None:
                existing = db.query(User).filter(User.email == data.email, User.id != user_id).first()
                if existing:
                    raise HTTPException(status_code=409, detail="Email already exists")
                target_user.email = data.email
            if data.role is not None:
                target_user.role = _normalize_role(data.role)
            if data.is_papa is not None:
                target_user.is_papa = data.is_papa
            if data.plan is not None:
                target_user.plan = data.plan

            if data.status is not None:
                acct_status, _reason_unused = _normalize_status_to_db(data.status)
                try:
                    setattr(target_user, 'account_status', acct_status)
                except Exception:
                    pass
                try:
                    setattr(target_user, 'is_active', True if acct_status == 'active' else False)
                except Exception:
                    pass
                try:
                    now = int(time.time())
                    setattr(target_user, 'locked_until', 0 if acct_status == 'active' else (now + 10 * 365 * 24 * 3600))
                except Exception:
                    pass
            
            target_user.updated_at = int(time.time())
            
            db.commit()
            
            # Audit
            write_audit("user_updated", actor_id=int(user.get("id") or 0), target_type="user", target_id=user_id)
            
            return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/{user_id}")
def delete_user(user_id: int, user = Depends(get_current_user_required)):
    """Delete user (admin only)"""
    require_role(user, {"creator"})
    
    try:
        with SessionLocal() as db:
            target_user = db.query(User).filter(User.id == user_id).first()
            
            if not target_user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Prevent self-deletion
            if target_user.id == user.get("id"):
                raise HTTPException(status_code=400, detail="Cannot delete yourself")
            
            db.delete(target_user)
            db.commit()
            
            # Audit
            write_audit("user_deleted", actor_id=int(user.get("id") or 0), target_type="user", target_id=user_id)
            
            return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
