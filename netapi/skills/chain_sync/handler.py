from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import os, subprocess


def run(action: str, args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pull or push chain blocks between peers.

    Actions:
      - "pull": args {"base": "https://peer"}
      - "push": args {"target": "user@host:/path/system/chain/", "delete": false}
    """
    root = Path.home() / "ki_ana"
    script = root / "system" / "chain_sync.py"
    if not script.exists():
        return {"ok": False, "error": "missing chain_sync.py"}

    if action == "pull":
        base = str(args.get("base") or os.getenv("CHAIN_PEER_BASE") or "").strip()
        if not base:
            return {"ok": False, "error": "missing base"}
        proc = subprocess.run(["python3", str(script), "pull", "--base", base], capture_output=True, text=True)
        return {"ok": proc.returncode == 0, "rc": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:]}

    if action == "push":
        target = str(args.get("target") or os.getenv("CHAIN_PUSH_TARGET") or "").strip()
        if not target:
            return {"ok": False, "error": "missing target"}
        cmd = ["python3", str(script), "push", "--target", target]
        if bool(args.get("delete")):
            cmd.append("--delete")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return {"ok": proc.returncode == 0, "rc": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:]}

    return {"ok": False, "error": "unknown_action", "action": action}

