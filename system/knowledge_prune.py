#!/usr/bin/env python3
from __future__ import annotations
"""
Prune old knowledge blocks by TTL.
- TTL days via env KI_KNOWLEDGE_TTL_DAYS (default 365)
- Optional CLI: --days N overrides env
"""
import os, sys, time, argparse
from pathlib import Path

# Ensure we can import netapi
KI_ROOT = Path(os.getenv('KI_ROOT', str(Path.home() / 'ki_ana')))
sys.path.insert(0, str(KI_ROOT))

from netapi.db import SessionLocal, init_db
from netapi.models import KnowledgeBlock


def prune(days: int) -> int:
    init_db()
    ttl_sec = max(1, int(days)*86400)
    cutoff = int(time.time()) - ttl_sec
    removed = 0
    with SessionLocal() as db:
        rows = db.query(KnowledgeBlock).filter(KnowledgeBlock.ts < cutoff).all()
        for r in rows:
            try:
                db.delete(r)
                removed += 1
            except Exception:
                pass
        db.commit()
    print(f"Pruned {removed} knowledge blocks older than {days} days (cutoff ts={cutoff})")
    return removed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=None, help='TTL in days (overrides env)')
    args = ap.parse_args()
    days_env = None
    try:
        days_env = int(os.getenv('KI_KNOWLEDGE_TTL_DAYS', '365'))
    except Exception:
        days_env = 365
    days = int(args.days if args.days is not None else days_env)
    return 0 if prune(days) >= 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
