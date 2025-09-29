#!/usr/bin/env python3
import argparse, json, shutil
from pathlib import Path

BASE   = Path.home() / "ki_ana"
SKILLS = BASE / "skills"
PROP   = SKILLS / "proposals"

def deploy(id_):
    src = SKILLS / "staging" / id_
    dst = SKILLS / id_
    if not src.exists(): raise SystemExit("Staging-Skill fehlt.")
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(src, dst)
    p = PROP / f"{id_}.proposal.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        d["status"] = "deployed"
        p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    print("✅ Deployed:", dst)

def disable(id_):
    src = SKILLS / id_
    dst = SKILLS / "disabled" / id_
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists(): raise SystemExit("Skill nicht aktiv.")
    if dst.exists(): shutil.rmtree(dst)
    shutil.move(str(src), str(dst))
    p = PROP / f"{id_}.proposal.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        d["status"] = "disabled"
        p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    print("🛑 Disabled:", dst)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["deploy","disable"])
    ap.add_argument("--id", required=True)
    a = ap.parse_args()
    if a.action=="deploy": deploy(a.id)
    else: disable(a.id)

if __name__ == "__main__":
    main()
