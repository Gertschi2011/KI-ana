#!/usr/bin/env python3
"""
Small helper to set a user's role in the local SQLite DB.

Usage:
  python3 ki_ana/tools/set_user_role.py --username <name> --role creator
  python3 ki_ana/tools/set_user_role.py --email <addr>    --role admin

DB path: /home/kiana/ki_ana/netapi/users.db
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

BASE = Path('/home/kiana/ki_ana')
DB_URL = f"sqlite:///{BASE / 'netapi' / 'users.db'}"

engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

from ki_ana.netapi.models import Base, User  # reuse model

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--username')
    ap.add_argument('--email')
    ap.add_argument('--role', required=True, help='creator | admin | family | user')
    args = ap.parse_args()

    if not args.username and not args.email:
        print('Provide --username or --email', file=sys.stderr)
        sys.exit(2)

    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        q = select(User)
        if args.username:
            q = q.where(User.username == args.username)
        if args.email:
            q = q.where(User.email == args.email)
        u = s.execute(q).scalars().first()
        if not u:
            print('User not found', file=sys.stderr)
            sys.exit(1)
        old = u.role
        u.role = args.role
        s.add(u)
        s.commit()
        print(f"OK: user id={u.id} username={u.username} role {old} -> {u.role}")

if __name__ == '__main__':
    main()

