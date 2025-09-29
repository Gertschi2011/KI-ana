# netapi/modules/kernel/scheduler.py
from __future__ import annotations
"""
Lightweight job scheduler for KI_ana kernel.
- Stores jobs in system/cron/jobs.json
- Supports either {"every_seconds": N} or {"cron": "*/5 * * * *"}
- Uses croniter if available; otherwise cron expressions are ignored
- Runs jobs by calling Kernel.exec(skill, action, args, role="admin")
"""
import asyncio
import json
import time
import uuid
import contextlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional
import os

# --- Optional cron support ---------------------------------------------------
try:
    from croniter import croniter  # type: ignore
    HAS_CRON = True
except Exception:
    croniter = None  # type: ignore
    HAS_CRON = False

# Kernel import (used to dispatch jobs)
from .core import KERNEL

# --- Storage -----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CRON_DIR = PROJECT_ROOT / "system" / "cron"
CRON_FILE = CRON_DIR / "jobs.json"
CRON_DIR.mkdir(parents=True, exist_ok=True)
if not CRON_FILE.exists():
    CRON_FILE.write_text("[]", encoding="utf-8")


@dataclass
class Job:
    id: str
    skill: str
    action: str
    args: Dict[str, Any]
    enabled: bool = True
    schedule: Dict[str, Any] = None  # {"every_seconds": 3600} or {"cron": "*/5 * * * *"}
    last_run: Optional[float] = None
    next_run: Optional[float] = None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Job":
        return Job(
            id=str(d.get("id") or f"J_{uuid.uuid4().hex[:8]}"),
            skill=str(d["skill"]),
            action=str(d["action"]),
            args=dict(d.get("args") or {}),
            enabled=bool(d.get("enabled", True)),
            schedule=dict(d.get("schedule") or {}),
            last_run=d.get("last_run"),
            next_run=d.get("next_run"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --- Persistence helpers -----------------------------------------------------

def _load() -> List[Job]:
    try:
        data = json.loads(CRON_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [Job.from_dict(x) for x in data]
    except Exception:
        return []


def _save(jobs: List[Job]) -> None:
    CRON_FILE.write_text(
        json.dumps([j.to_dict() for j in jobs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _compute_next(j: Job, now: float) -> Optional[float]:
    sch = j.schedule or {}
    if "every_seconds" in sch:
        try:
            sec = max(1, int(sch.get("every_seconds") or 0))
        except Exception:
            sec = 60
        base = j.last_run or now
        return max(now, base + sec)
    if "cron" in sch and HAS_CRON:
        try:
            it = croniter(str(sch["cron"]), now)  # type: ignore[arg-type]
            return float(it.get_next(float))
        except Exception:
            return None
    return None


# --- Scheduler ---------------------------------------------------------------
class Scheduler:
    def __init__(self) -> None:
        self._jobs: List[Job] = _load()
        self._task: Optional[asyncio.Task] = None
        # pre-compute next_run for existing jobs
        now = time.time()
        for j in self._jobs:
            if j.enabled and not j.next_run:
                j.next_run = _compute_next(j, now)
        _save(self._jobs)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            # asyncio.CancelledError inherits from BaseException – suppress explicitly
            with contextlib.suppress(BaseException):
                await self._task
        self._task = None

    async def reload(self) -> None:
        await self.stop()
        self._jobs = _load()
        now = time.time()
        for j in self._jobs:
            if j.enabled:
                j.next_run = _compute_next(j, now)
        _save(self._jobs)
        await self.start()

    async def _loop(self) -> None:
        while True:
            now = time.time()
            ran_any = False
            # Emergency stop: pause all job executions
            try:
                root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
                if (root / "emergency_stop").exists():
                    await asyncio.sleep(1.0)
                    continue
            except Exception:
                pass
            for j in self._jobs:
                if not j.enabled:
                    continue
                if j.next_run and now + 0.01 >= j.next_run:
                    # execute
                    try:
                        await KERNEL.exec(j.skill, j.action, j.args, role="admin")
                    except Exception:
                        # swallow job exceptions – they shouldn't kill the loop
                        pass
                    j.last_run = now
                    j.next_run = _compute_next(j, now)
                    ran_any = True
            if ran_any:
                _save(self._jobs)
            await asyncio.sleep(1.0)

    # --- API -----------------------------------------------------------------
    def list(self) -> List[Dict[str, Any]]:
        return [j.to_dict() for j in self._jobs]

    def add(self, job: Dict[str, Any]) -> Dict[str, Any]:
        j = Job.from_dict(job)
        j.enabled = bool(job.get("enabled", True))
        j.next_run = _compute_next(j, time.time()) if j.enabled else None
        self._jobs.append(j)
        _save(self._jobs)
        return j.to_dict()

    def delete(self, job_id: str) -> bool:
        n = len(self._jobs)
        self._jobs = [j for j in self._jobs if j.id != job_id]
        changed = len(self._jobs) < n
        if changed:
            _save(self._jobs)
        return changed

    def toggle(self, job_id: str, enabled: bool) -> Optional[Dict[str, Any]]:
        now = time.time()
        for j in self._jobs:
            if j.id == job_id:
                j.enabled = enabled
                j.next_run = _compute_next(j, now) if enabled else None
                _save(self._jobs)
                return j.to_dict()
        return None


SCHED = Scheduler()
