#!/usr/bin/env python3
from __future__ import annotations
"""
Simple chain peer sync utility.

Pull mode (HTTP):
  python3 system/chain_sync.py pull --base https://peer.example.org

Push mode (rsync):
  python3 system/chain_sync.py push --target user@host:/home/user/ki_ana/system/chain/

The pull mode uses /viewer/api/blocks and /viewer/api/block/by-id/{id}
to fetch chain blocks and verify their hashes before saving.
"""
import argparse
import json
import os
import sys
import hashlib
from pathlib import Path
from typing import Dict, Any, List

import requests

ROOT = Path.home() / "ki_ana"
CHAIN_DIR = ROOT / "system" / "chain"
CHAIN_DIR.mkdir(parents=True, exist_ok=True)


def _sha256_canonical(obj: Dict[str, Any]) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def pull_http(base: str) -> int:
    """Fetch remote chain blocks and store locally if missing/invalid.
    Returns number of blocks written.
    """
    base = base.rstrip("/")
    r = requests.get(f"{base}/viewer/api/blocks", timeout=15)
    r.raise_for_status()
    data = r.json()
    items = data.get("items") or []
    # consider only chain origin
    chain_items = [it for it in items if (it.get("origin") or "").startswith("system/chain")]
    written = 0
    for it in chain_items:
        bid = str(it.get("id") or "").strip()
        if not bid:
            continue
        local = CHAIN_DIR / f"{bid}.json"
        if local.exists():
            try:
                obj = json.loads(local.read_text(encoding="utf-8"))
                calc = _sha256_canonical(obj)
                if calc == (obj.get("hash") or ""):
                    continue  # already good
            except Exception:
                pass
        # fetch block JSON by id
        br = requests.get(f"{base}/viewer/api/block/by-id/{bid}", timeout=20)
        if br.status_code != 200:
            continue
        payload = br.json() or {}
        block = payload.get("block") or {}
        if not isinstance(block, dict):
            continue
        calc = _sha256_canonical(block)
        if calc != (block.get("hash") or ""):
            print(f"skip {bid}: hash mismatch", file=sys.stderr)
            continue
        local.write_text(json.dumps(block, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1
    return written


def push_rsync(target: str, delete: bool = False) -> int:
    import subprocess
    args = [
        "rsync", "-az", "--info=stats1", *( ["--delete"] if delete else [] ),
        str(CHAIN_DIR) + "/",
        target,
    ]
    proc = subprocess.run(args)
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_pull = sub.add_parser("pull", help="Pull chain via HTTP")
    p_pull.add_argument("--base", required=True, help="Base URL of remote peer (e.g., https://host)")

    p_push = sub.add_parser("push", help="Push chain via rsync")
    p_push.add_argument("--target", required=True, help="rsync target (user@host:/path/system/chain/)")
    p_push.add_argument("--delete", action="store_true", help="delete extras on target")

    args = ap.parse_args()
    if args.cmd == "pull":
        n = pull_http(args.base)
        print(f"pulled {n} block(s)")
        return 0
    if args.cmd == "push":
        rc = push_rsync(args.target, delete=args.delete)
        return rc
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

