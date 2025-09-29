#!/usr/bin/env python3
from __future__ import annotations
"""
plan_enforcer.py – Auto-suspend users whose paid plan expired (plan_until < now).

- Sets status = 'suspended' and suspended_reason = 'Plan abgelaufen' when applicable
- Idempotent (will not change users already non-active)
- Writes AdminAudit entries (best-effort)

Usage:
  python3 system/plan_enforcer.py [--dry-run]

Environment:
  KI_ROOT (optional)
  DATABASE_URL (optional)
"""
import argparse
import os
import sys
import time
import json

# Ensure KI_ROOT on sys.path
try:
    from pathlib import Path
    KI_ROOT = os.getenv("KI_ROOT") or str(Path.home() / "ki_ana")
    sys.path.insert(0, KI_ROOT)
except Exception:
    pass

from netapi.db import SessionLocal  # type: ignore
from netapi.models import User, AdminAudit  # type: ignore


def write_audit(db, actor_id: int, action: str, target_id: int, meta: dict) -> None:
    try:
        aa = AdminAudit(
            ts=int(time.time()),
            actor_user_id=int(actor_id or 0),
            action=action[:64],
            target_type="user",
            target_id=int(target_id or 0),
            meta=json.dumps(meta, ensure_ascii=False)[:4000],
        )
        db.add(aa)
    except Exception:
        pass


def enforce(dry_run: bool = False) -> int:
    now = int(time.time())
    updated = 0
    with SessionLocal() as db:
        # Users whose plan expired and are still active
        rows = db.query(User).filter((User.plan_until > 0), (User.plan_until < now), (User.status == 'active')).all()
        for u in rows:
            if dry_run:
                updated += 1
                continue
            u.status = 'suspended'
            u.suspended_reason = 'Plan abgelaufen'
            u.updated_at = now
            db.add(u)
            write_audit(db, actor_id=0, action="auto_suspend_plan_expired", target_id=u.id, meta={"plan_until": int(u.plan_until or 0)})
            updated += 1
        if not dry_run:
            db.commit()
    return updated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    n = enforce(dry_run=args.dry_run)
    if args.dry_run:
        print(f"[plan_enforcer] would suspend {n} users")
    else:
        print(f"[plan_enforcer] suspended {n} users")


if __name__ == '__main__':
    main()
