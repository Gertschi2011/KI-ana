#!/usr/bin/env python3
from __future__ import annotations
"""
telemetry_prune.py – Delete browser_errors older than N days (default: 30)

Usage:
  python3 system/telemetry_prune.py [--days 30]

Runs standalone, without HTTP. Safe to schedule via systemd timer.
"""
import argparse
import os
import sys
import time

# Make netapi importable (assumes KI_ROOT env or default ~/ki_ana)
try:
    from pathlib import Path
    KI_ROOT = os.getenv("KI_ROOT") or str(Path.home() / "ki_ana")
    sys.path.insert(0, KI_ROOT)
except Exception:
    pass

from netapi.db import SessionLocal  # type: ignore
from netapi.models import BrowserError  # type: ignore


def prune_old(days: int = 30) -> int:
    try:
        cutoff = int(time.time()) - max(1, int(days)) * 86400
        from sqlalchemy import delete
        with SessionLocal() as db:
            res = db.execute(delete(BrowserError).where(BrowserError.ts < cutoff))
            db.commit()
            return int(getattr(res, 'rowcount', 0) or 0)
    except Exception as e:
        print("[telemetry_prune] error:", e)
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=int(os.getenv('KI_TELEMETRY_TTL_DAYS', '30')))
    args = ap.parse_args()
    n = prune_old(args.days)
    print(f"[telemetry_prune] deleted {n} rows older than {args.days} days")


if __name__ == '__main__':
    main()
