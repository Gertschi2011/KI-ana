#!/usr/bin/env python3
from __future__ import annotations
"""
device_events_stats_rollup.py – Hourly rollup of queued_total and pruned_total.

Usage:
  python3 system/device_events_stats_rollup.py

Collects:
- queued_total: count of device_events with delivered_at == 0
- pruned_total: sum of devices.events_pruned_total
Writes/upserts into device_events_stats keyed by ts_hour (epoch truncated to hour).
"""
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
from netapi.models import DeviceEvent, Device  # type: ignore


def epoch_hour(ts: int | None = None) -> int:
    t = int(ts or time.time())
    return t - (t % 3600)


def collect_totals(db) -> tuple[int, int]:
    # queued_total
    try:
        queued_total = int(db.query(DeviceEvent).filter(DeviceEvent.delivered_at == 0).count() or 0)
    except Exception:
        queued_total = 0
    # pruned_total
    try:
        pruned_total = int(sum(int(getattr(d, 'events_pruned_total', 0) or 0) for d in db.query(Device).all()))
    except Exception:
        pruned_total = 0
    return queued_total, pruned_total


def upsert_stats(ts_h: int, queued: int, pruned: int) -> None:
    from sqlalchemy import text as _t
    now = int(time.time())
    with SessionLocal() as db:
        try:
            row = db.execute(_t("SELECT ts_hour FROM device_events_stats WHERE ts_hour=:h"), {"h": ts_h}).fetchone()
            if row:
                db.execute(
                    _t("UPDATE device_events_stats SET queued_total=:q, pruned_total=:p, updated_at=:u WHERE ts_hour=:h"),
                    {"q": queued, "p": pruned, "u": now, "h": ts_h},
                )
            else:
                db.execute(
                    _t("INSERT INTO device_events_stats(ts_hour, queued_total, pruned_total, created_at, updated_at) VALUES(:h,:q,:p,:c,:u)"),
                    {"h": ts_h, "q": queued, "p": pruned, "c": now, "u": now},
                )
            db.commit()
        except Exception as e:
            print("[device_events_stats_rollup] upsert error:", e)
            db.rollback()


def main():
    with SessionLocal() as db:
        queued, pruned = collect_totals(db)
    h = epoch_hour()
    upsert_stats(h, queued, pruned)
    print(f"[device_events_stats_rollup] ts_hour={h} queued_total={queued} pruned_total={pruned}")


if __name__ == '__main__':
    main()
