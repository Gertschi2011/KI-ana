#!/usr/bin/env python3
"""
Simple crawler job worker.

Leases jobs from the local DB table 'jobs' (types: 'crawler.run', 'crawler.promote'),
executes them using system.crawler_loop helpers, and updates job status with
basic retry/backoff.

Run it next to the API process:
  $ python -m ki_ana.system.crawler_worker

Environment:
  KI_WORKER_MAX_ATTEMPTS (default 5)
  KI_WORKER_LEASE_SECONDS (default 60)
  KI_WORKER_IDLE_SLEEP (default 2)
"""
from __future__ import annotations
import os, time, json, traceback
from typing import Dict, Any

from ..netapi.db import SessionLocal
from ..netapi.models import Job
from pathlib import Path
import socket

# Try load crawler helpers (same code path as API router)
try:
    from ki_ana.system.crawler_loop import run_crawler_once, promote_crawled_to_blocks  # type: ignore
except Exception:
    from importlib.machinery import SourceFileLoader as _Loader  # type: ignore
    from pathlib import Path as _Path
    _p = _Path.home() / "ki_ana" / "system" / "crawler_loop.py"
    _mod = _Loader("crawler_loop", str(_p)).load_module()  # type: ignore
    run_crawler_once = getattr(_mod, "run_crawler_once")  # type: ignore
    promote_crawled_to_blocks = getattr(_mod, "promote_crawled_to_blocks")  # type: ignore


MAX_ATTEMPTS = int(os.getenv("KI_WORKER_MAX_ATTEMPTS", "5"))
LEASE_SECONDS = int(os.getenv("KI_WORKER_LEASE_SECONDS", "60"))
IDLE_SLEEP = float(os.getenv("KI_WORKER_IDLE_SLEEP", "2"))
ALLOWED = {"crawler.run", "crawler.promote"}


def _now() -> int:
    return int(time.time())


def _backoff(attempts: int) -> int:
    # 5, 10, 20, 40, 80, 160, 320, capped at 3600
    return min(3600, 5 * (2 ** min(7, attempts)))


def _lease_one(db) -> Job | None:
    now = _now()
    j = (
        db.query(Job)
        .filter(Job.type.in_(list(ALLOWED)), ((Job.status == "queued") | (Job.lease_until < now)))
        .order_by(Job.priority.desc(), Job.id.asc())
        .first()
    )
    if not j:
        return None
    j.status = "leased"
    j.lease_until = now + LEASE_SECONDS
    j.updated_at = now
    db.add(j); db.commit(); db.refresh(j)
    return j


def _update_done(db, j: Job):
    j.status = "done"; j.lease_until = 0; j.updated_at = _now(); j.error = ""
    db.add(j); db.commit()


def _update_fail(db, j: Job, err: str):
    j.attempts = int(j.attempts or 0) + 1
    j.error = (err or "")[:2000]
    now = _now()
    if j.attempts >= MAX_ATTEMPTS:
        j.status = "failed"; j.lease_until = 0
    else:
        j.status = "queued"; j.lease_until = now + _backoff(j.attempts)
    j.updated_at = now
    db.add(j); db.commit()


def _write_heartbeat(last: dict | None = None) -> None:
    try:
        root = Path.home() / "ki_ana"
        logdir = root / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        hb = {
            "name": "crawler",
            "ts": _now(),
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "job_types": sorted(list(ALLOWED)),
        }
        if last:
            hb.update(last)
        (logdir / "worker_heartbeat_crawler.json").write_text(json.dumps(hb, ensure_ascii=False), encoding="utf-8")
        # Also POST to local API (non-fatal if offline)
        try:
            import urllib.request as _ur
            data = json.dumps({
                "name": hb.get("name"),
                "type": "crawler",
                "status": hb.get("last_status") or "ok",
                "pid": hb.get("pid"),
                "job_types": hb.get("job_types"),
                "ts": hb.get("ts"),
            }).encode("utf-8")
            req = _ur.Request("http://127.0.0.1:8000/api/jobs/heartbeat", data=data, headers={"Content-Type":"application/json"})
            _ur.urlopen(req, timeout=2)
        except Exception:
            pass
    except Exception:
        pass


def _exec(j: Job) -> None:
    payload: Dict[str, Any] = {}
    try:
        payload = json.loads(j.payload or "{}")
    except Exception:
        payload = {}
    if j.type == "crawler.run":
        run_crawler_once()
    elif j.type == "crawler.promote":
        promote_crawled_to_blocks()
    else:
        raise RuntimeError(f"unsupported job type: {j.type}")


def main():
    print("[crawler_worker] starting … allowed:", ", ".join(sorted(ALLOWED)))
    last_hb = 0
    while True:
        try:
            with SessionLocal() as db:
                now = _now()
                if now - last_hb >= 10:
                    _write_heartbeat(None); last_hb = now
                j = _lease_one(db)
                if not j:
                    time.sleep(IDLE_SLEEP)
                    # ensure periodic heartbeat even if idle for long
                    now = _now()
                    if now - last_hb >= 10:
                        _write_heartbeat(None); last_hb = now
                    continue
                print(f"[crawler_worker] leased job {j.id} type={j.type} attempts={j.attempts}")
                try:
                    _exec(j)
                    _update_done(db, j)
                    print(f"[crawler_worker] done job {j.id}")
                    _write_heartbeat({"last_job_id": j.id, "last_type": j.type, "last_status": "done"})
                    last_hb = _now()
                except Exception as e:
                    tb = traceback.format_exc()[-1000:]
                    print(f"[crawler_worker] fail job {j.id}: {e}\n{tb}")
                    _update_fail(db, j, f"{type(e).__name__}: {e}")
                    _write_heartbeat({"last_job_id": j.id, "last_type": j.type, "last_status": "failed"})
                    last_hb = _now()
        except KeyboardInterrupt:
            print("[crawler_worker] exiting (KeyboardInterrupt)")
            break
        except Exception as e:
            print("[crawler_worker] outer error:", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
