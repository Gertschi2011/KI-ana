#!/usr/bin/env python3
"""One-time admin helper: set a user's role safely.

Usage:
  python3 scripts/set_role.py gerald creator

Notes:
- This is intentionally a manual/ops action (no auto-escalation at app start).
- Works with the netapi DB schema (SQLAlchemy models).
"""

from __future__ import annotations

import sys
from datetime import datetime


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: python3 scripts/set_role.py <username|email> <role>")
        return 2

    ident = (argv[1] or "").strip()
    role = (argv[2] or "").strip().lower()

    if not ident or not role:
        print("❌ Missing username/email or role")
        return 2

    allowed = {"user", "family", "papa", "creator", "admin"}
    if role not in allowed:
        print(f"❌ Role must be one of: {', '.join(sorted(allowed))}")
        return 2

    try:
        from ki_ana.netapi.db import SessionLocal  # type: ignore
        from ki_ana.netapi.models import User  # type: ignore
    except Exception:
        # fallback when executed from repo root (common)
        from netapi.db import SessionLocal  # type: ignore
        from netapi.models import User  # type: ignore

    ident_l = ident.lower()

    with SessionLocal() as db:
        user = (
            db.query(User)
            .filter((User.username.ilike(ident_l)) | (User.email.ilike(ident_l)))
            .first()
        )
        if not user:
            print(f"❌ User not found: {ident}")
            return 1

        old = (getattr(user, "role", None) or "user")
        setattr(user, "role", role)
        if hasattr(user, "updated_at"):
            try:
                setattr(user, "updated_at", datetime.utcnow())
            except Exception:
                pass
        db.add(user)
        db.commit()

        print("✅ Updated user")
        print(f"  username: {getattr(user, 'username', None)}")
        print(f"  email:    {getattr(user, 'email', None)}")
        print(f"  role:     {old} -> {role}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
