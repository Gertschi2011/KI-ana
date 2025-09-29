# netapi/modules/kernel/core.py
from __future__ import annotations
import asyncio, importlib, json, os, traceback, sys, contextlib, shlex, time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR   = PROJECT_ROOT / "netapi" / "skills"

# Logs unter ~/ki_ana/logs
LOG_DIR    = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
KERNEL_LOG = LOG_DIR / "kernel.log"

# ENV-Schalter für Subprozesse
SUBPROC_TIMEOUT = float(os.getenv("KERNEL_SUBPROC_TIMEOUT", "6.0"))   # Sekunden
SUBPROC_WRAPPER = os.getenv("KERNEL_SUBPROC_WRAPPER", "").strip()     # z.B. 'bwrap ...' oder 'firejail ...'

@dataclass
class SkillSpec:
    name: str
    version: str
    entrypoint: str          # "package.module:func"
    capabilities: list[str]
    schedule_every: Optional[int] = None  # seconds
    run_mode: str = "inproc"              # "inproc" | "subproc"

class Kernel:
    def __init__(self) -> None:
        self.skills: Dict[str, SkillSpec] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running = False

    # --- Logging -------------------------------------------------------------
    def _log(self, msg: str) -> None:
        try:
            with KERNEL_LOG.open("a", encoding="utf-8") as f:
                f.write(msg.rstrip() + "\n")
        except Exception:
            # als allerletzter Fallback auf stderr
            print(msg, file=sys.stderr)

    def _audit(self, payload: Dict[str, Any]) -> None:
        try:
            audit = LOG_DIR / "audit_skill.jsonl"
            with audit.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # --- Skill Discovery / Manifest -----------------------------------------
    def _load_manifest(self, p: Path) -> Optional[SkillSpec]:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            ep    = str(data["entrypoint"])
            sched = data.get("schedule") or {}
            every = None
            if isinstance(sched, dict):
                try:
                    every = int(sched.get("every_seconds") or 0) or None
                except Exception:
                    every = None
            return SkillSpec(
                name=str(data["name"]),
                version=str(data.get("version", "0.0.0")),
                entrypoint=ep,
                capabilities=list(data.get("capabilities") or []),
                schedule_every=every,
                run_mode=str(data.get("run_mode", "inproc")).lower(),
            )
        except Exception as e:
            self._log(f"[manifest-error] {p}: {e}")
            return None

    def _resolve_entrypoint(self, spec: SkillSpec) -> Callable[..., Any]:
        mod_path, fn_name = spec.entrypoint.split(":", 1)
        mod = importlib.import_module(mod_path)
        fn  = getattr(mod, fn_name)
        if not callable(fn):
            raise TypeError(f"entrypoint not callable: {spec.entrypoint}")
        return fn

    # --- Lifecycle -----------------------------------------------------------
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.load_skills()

        # Legacy: einfache Periodics aus manifest.every_seconds
        for name, spec in self.skills.items():
            if spec.schedule_every:
                self._tasks[name] = asyncio.create_task(self._run_periodic(spec))

        # Erweiterter Scheduler (Jobs API)
        try:
            from .scheduler import SCHED
            await SCHED.start()
        except Exception:
            self._log("[kernel] scheduler start failed\n" + traceback.format_exc())

        self._log("[kernel] started")

        # Optional: auto-add chain pull job from env
        try:
            from .scheduler import SCHED
            peer = os.getenv("CHAIN_PEER_BASE", "").strip()
            interval = int(os.getenv("CHAIN_PULL_EVERY", "600"))
            if peer:
                existing = [j for j in SCHED.list() if j.get('skill') == 'chain_sync' and j.get('action') == 'pull']
                if not existing:
                    SCHED.add({
                        'skill': 'chain_sync',
                        'action': 'pull',
                        'args': {'base': peer},
                        'enabled': True,
                        'schedule': {'every_seconds': max(60, interval)},
                    })
                    self._log(f"[kernel] added chain_sync pull job (base={peer})")
        except Exception:
            pass

    async def stop(self) -> None:
        # Scheduler stoppen
        with contextlib.suppress(Exception):
            from .scheduler import SCHED
            await SCHED.stop()

        for t in list(self._tasks.values()):
            t.cancel()
        self._tasks.clear()
        self._running = False
        self._log("[kernel] stopped")

    def load_skills(self) -> None:
        self.skills.clear()
        if not SKILLS_DIR.exists():
            return
        for mp in SKILLS_DIR.glob("*/manifest.json"):
            spec = self._load_manifest(mp)
            if spec:
                self.skills[spec.name] = spec

    async def reload(self) -> None:
        await self.stop()
        self.load_skills()
        await self.start()
        self._log("[kernel] reloaded")

    async def _run_periodic(self, spec: SkillSpec) -> None:
        while self._running:
            try:
                await self._call_skill(spec, action="scheduled", args={}, role="system")
            except Exception:
                self._log(f"[periodic-error] {spec.name}\n" + traceback.format_exc())
            await asyncio.sleep(spec.schedule_every or 60)

    # --- Public Exec ---------------------------------------------------------
    async def exec(self, skill: str, action: str, args: Dict[str, Any], role: str = "user") -> Dict[str, Any]:
        spec = self.skills.get(skill)
        if not spec:
            return {"ok": False, "error": "skill_not_found", "skill": skill}
        res = await self._call_skill(spec, action=action, args=args, role=role)
        try:
            self._audit({
                "ts": int(time.time()),
                "skill": skill,
                "action": action,
                "args": args,
                "role": role,
                "ok": bool(res.get("ok", True)),
                "error": res.get("error")
            })
        except Exception:
            pass
        return res

    # --- Dispatch ------------------------------------------------------------
    async def _call_skill(self, spec: SkillSpec, *, action: str, args: Dict[str, Any], role: str) -> Dict[str, Any]:
        if spec.run_mode == "subproc":
            return await self._call_subproc(spec, action=action, args=args, role=role)

        # In-Process (sicher, aber ohne Sandbox)
        try:
            fn = self._resolve_entrypoint(spec)
            ctx = {"role": role, "capabilities": spec.capabilities, "skill": spec.name, "version": spec.version}
            if asyncio.iscoroutinefunction(fn):
                res = await fn(action=action, args=args, ctx=ctx)
            else:
                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(None, fn, action, args, ctx)
            if not isinstance(res, dict):
                res = {"result": res}
            return {"ok": True, **res}
        except Exception:
            self._log(f"[skill-error] {spec.name}\n" + traceback.format_exc())
            return {"ok": False, "error": "skill_exception", "skill": spec.name}

    # --- Subprocess Execution (mit Wrapper & Timeout via ENV) ---------------
    async def _call_subproc(self, spec: SkillSpec, *, action: str, args: Dict[str, Any], role: str) -> Dict[str, Any]:
        payload = {
            "entrypoint": spec.entrypoint,
            "action": action,
            "args": args,
            "ctx": {"role": role, "capabilities": spec.capabilities, "skill": spec.name, "version": spec.version},
            "limits": {"cpu": 3, "mem_mb": 256, "nfile": 64},
        }

        base_cmd = [sys.executable, "-m", "netapi.modules.kernel.worker"]
        cmd = (shlex.split(SUBPROC_WRAPPER) + base_cmd) if SUBPROC_WRAPPER else base_cmd

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(
                proc.communicate(json.dumps(payload).encode("utf-8")),
                timeout=SUBPROC_TIMEOUT,
            )
        except asyncio.TimeoutError:
            self._log(f"[subproc-timeout] {spec.name} after {SUBPROC_TIMEOUT}s")
            return {"ok": False, "error": "subproc_timeout", "timeout_s": SUBPROC_TIMEOUT, "skill": spec.name}
        except Exception as e:
            self._log(f"[subproc-error] {spec.name}: {e}")
            return {"ok": False, "error": "subproc_spawn", "detail": str(e), "skill": spec.name}

        if proc.returncode != 0:
            stderr_txt = err.decode("utf-8", "replace")
            self._log(f"[subproc-rc] {spec.name} rc={proc.returncode}\n{stderr_txt}")
            return {"ok": False, "error": "subproc_rc", "rc": proc.returncode, "stderr": stderr_txt, "skill": spec.name}

        try:
            data = json.loads(out.decode("utf-8"))
            if isinstance(data, dict):
                return data
            return {"ok": True, "result": data}
        except Exception:
            self._log(f"[subproc-parse] {spec.name} invalid JSON")
            return {"ok": False, "error": "subproc_parse", "skill": spec.name}

# Singleton
KERNEL = Kernel()
