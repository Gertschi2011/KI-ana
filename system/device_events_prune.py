#!/usr/bin/env python3
from __future__ import annotations
"""
device_events_prune.py – Prune device_events by TTL and max depth per device.

Usage:
  python3 system/device_events_prune.py [--days 7] [--max 100]

Reads defaults from env:
  KI_DEVICE_EVENTS_TTL_DAYS (default 7)
  KI_DEVICE_EVENTS_MAX_DEPTH (default 100)

Runs standalone, without HTTP. Safe to schedule via systemd timer.
"""
import argparse
import os
import sys
import time
from typing import Optional, List

# Make netapi importable (assumes KI_ROOT env or default ~/ki_ana)
try:
    from pathlib import Path
    KI_ROOT = os.getenv("KI_ROOT") or str(Path.home() / "ki_ana")
    sys.path.insert(0, KI_ROOT)
except Exception:
    pass

from netapi.db import SessionLocal  # type: ignore
from netapi.models import DeviceEvent, Device  # type: ignore


def prune_ttl(days: int) -> int:
    """Delete events older than days."""
    try:
        cutoff = int(time.time()) - max(1, int(days)) * 86400
        from sqlalchemy import select, delete
        with SessionLocal() as db:
            rows = db.execute(
                select(DeviceEvent.id, DeviceEvent.device_id)
                .where(DeviceEvent.ts < cutoff)
            ).fetchall()
            if not rows:
                return 0
            # group by device_id
            by_dev = {}
            for _id, did in rows:
                by_dev.setdefault(int(did), []).append(int(_id))
            total = 0
            for did, ids in by_dev.items():
                if not ids:
                    continue
                res = db.execute(delete(DeviceEvent).where(DeviceEvent.id.in_(ids)))
                total += int(getattr(res, 'rowcount', 0) or 0)
                # bump device metric
                try:
                    dev = db.query(Device).filter(Device.id == int(did)).first()
                    if dev:
                        dev.events_pruned_total = int(getattr(dev, 'events_pruned_total', 0) or 0) + len(ids)
                        db.add(dev)
                except Exception:
                    pass
            db.commit()
            return total
    except Exception as e:
        print("[device_events_prune] ttl error:", e)
        return 0


def prune_depth(max_depth: int) -> int:
    """For each device, keep only newest max_depth events by ts; delete older ones."""
    max_depth = max(1, int(max_depth))
    deleted = 0
    try:
        from sqlalchemy import select
        with SessionLocal() as db:
            # Get distinct device_ids having more than max_depth events
            device_ids = [row[0] for row in db.execute(select(DeviceEvent.device_id).distinct())]
            for did in device_ids:
                # Fetch ids ordered by ts asc (oldest first)
                rows = db.execute(
                    select(DeviceEvent.id)
                    .where(DeviceEvent.device_id == int(did))
                    .order_by(DeviceEvent.ts.asc(), DeviceEvent.id.asc())
                ).fetchall()
                if not rows:
                    continue
                if len(rows) <= max_depth:
                    continue
                to_delete_ids = [int(r[0]) for r in rows[:-max_depth]]
                if not to_delete_ids:
                    continue
                from sqlalchemy import delete
                res = db.execute(delete(DeviceEvent).where(DeviceEvent.id.in_(to_delete_ids)))
                n = int(getattr(res, 'rowcount', 0) or 0)
                # bump device metric
                try:
                    dev = db.query(Device).filter(Device.id == int(did)).first()
                    if dev and n:
                        dev.events_pruned_total = int(getattr(dev, 'events_pruned_total', 0) or 0) + n
                        db.add(dev)
                except Exception:
                    pass
                db.commit()
                deleted += n
        return deleted
    except Exception as e:
        print("[device_events_prune] depth error:", e)
        return deleted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=int(os.getenv('KI_DEVICE_EVENTS_TTL_DAYS', '7')))
    ap.add_argument('--max', dest='max_depth', type=int, default=int(os.getenv('KI_DEVICE_EVENTS_MAX_DEPTH', '100')))
    args = ap.parse_args()

    n_ttl = prune_ttl(args.days)
    n_depth = prune_depth(args.max_depth)
    total = n_ttl + n_depth
    print(f"[device_events_prune] ttl_deleted={n_ttl} depth_deleted={n_depth} total={total} (days={args.days} max={args.max_depth})")


if __name__ == '__main__':
    main()
