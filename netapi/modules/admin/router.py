from __future__ import annotations
from fastapi import APIRouter, Depends
from typing import Any, Dict
import json, time

from ...deps import get_current_user_required, require_role
from ...db import SessionLocal
from ...models import AdminAudit

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
