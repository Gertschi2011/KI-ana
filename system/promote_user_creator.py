#!/usr/bin/env python3
"""
Promote a user to Creator role (role=tier='creator')

Usage examples:
  python3 system/promote_user_creator.py --username alice
  python3 system/promote_user_creator.py --id 3

Notes:
- Requires access to the same DB as the app (via netapi.db.SessionLocal)
- Safe to run multiple times (idempotent)
- Prints the previous and new role/tier
"""
import os
import sys
import argparse

# Make netapi importable (assumes KI_ROOT env or default ~/ki_ana)
try:
    from pathlib import Path
    KI_ROOT = os.getenv("KI_ROOT") or str(Path.home() / "ki_ana")
    sys.path.insert(0, KI_ROOT)
except Exception:
    pass

from netapi.db import SessionLocal  # type: ignore
from netapi.models import User  # type: ignore


def promote(user_id: int | None = None, username: str | None = None) -> int:
    if not user_id and not username:
        print("Provide --id or --username")
        return 2
    with SessionLocal() as db:
        q = db.query(User)
        if user_id:
            q = q.filter(User.id == int(user_id))
        elif username:
            q = q.filter(User.username == str(username))
        u = q.first()
        if not u:
            print("User not found")
            return 3
        before_role = getattr(u, 'role', None)
        before_tier = getattr(u, 'tier', None)
        u.role = 'creator'
        try:
            setattr(u, 'tier', 'creator')
        except Exception:
            pass
        db.add(u)
        db.commit()
        print(f"Promoted user id={u.id} username={u.username} role: {before_role} -> {u.role}, tier: {before_tier} -> {getattr(u,'tier', None)}")
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', type=int, default=None, help='User ID to promote')
    ap.add_argument('--username', type=str, default=None, help='Username to promote')
    args = ap.parse_args()
    sys.exit(promote(args.id, args.username))


if __name__ == '__main__':
    main()
