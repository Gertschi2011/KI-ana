#!/usr/bin/env python3
import argparse, json, subprocess, sys, os, resource
from pathlib import Path
from datetime import datetime

BASE    = Path.home() / "ki_ana"
SKILLS  = BASE / "skills"
PROP    = SKILLS / "proposals"
RUNNER  = BASE / "system" / "skill_runner.py"

def limit_resources():
    # 2 CPU-Sekunden, 256 MB RAM, kein Core-Dump
    resource.setrlimit(resource.RLIMIT_CPU, (2,2))
    resource.setrlimit(resource.RLIMIT_AS,  (256*1024*1024, 256*1024*1024))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))

def sandbox_run(skill_id: str) -> tuple[bool, str]:
    env = os.environ.copy()
    env["KIANA_SANDBOX"] = "1"
    try:
        # setrlimit nur in child über preexec_fn
        p = subprocess.run(
            ["python3", str(RUNNER), skill_id],
            capture_output=True, text=True, timeout=5, env=env, preexec_fn=limit_resources
        )
        ok = (p.returncode == 0)
        out = (p.stdout or "") + (p.stderr or "")
        return ok, out[-2000:]
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, f"Error: {e}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    args = ap.parse_args()

    stage = SKILLS / "staging" / args.id
    if not stage.exists():
        print("❌ Kein Staging-Skill gefunden:", stage)
        return 2

    ok, out = sandbox_run(args.id)
    propf = PROP / f"{args.id}.proposal.json"
    if propf.exists():
        d = json.loads(propf.read_text(encoding="utf-8"))
        d["sandbox"]["ok"] = bool(ok)
        d["sandbox"]["note"] = out.strip()[:2000]
        d["status"] = "tested" if ok else "proposed"
        propf.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    print(("✅ Sandbox OK" if ok else "❌ Sandbox FAIL") + "\n" + out)
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
