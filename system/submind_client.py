#!/usr/bin/env python3
from __future__ import annotations
"""
Minimal Submind client to ingest local findings to the Mother‑KI.

Usage examples:
  python3 system/submind_client.py --id kid-1 --key-file /home/kiana/ki_ana/subminds/kid-1/api.key
  python3 system/submind_client.py --id kid-1 --key ABC... --base http://127.0.0.1:8000

Behavior:
  - If subminds/<id>/outbox/*.json exists, sends these as items and moves to sent/ on success
  - Else, scans subminds/<id>/memory/long_term for recent facts and sends top N (default 5)

Outbox file format (JSON): {"title": str, "content": str, "url": "", "tags": ["..."]}
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

import requests

ROOT = Path.home() / "ki_ana"


def _load_key(sid: str, key: str | None, key_file: str | None) -> str:
    if key:
        return key
    if key_file:
        return Path(key_file).read_text().strip()
    # default location
    p = ROOT / "subminds" / sid / "api.key"
    if p.exists():
        return p.read_text().strip()
    env = os.getenv("SUBMIND_KEY")
    if env:
        return env.strip()
    raise SystemExit("No API key provided. Use --key, --key-file or create subminds/<id>/api.key")


def _collect_outbox(sid: str) -> List[Dict[str, Any]]:
    d = ROOT / "subminds" / sid / "outbox"
    if not d.exists():
        return []
    items: List[Dict[str, Any]] = []
    for p in sorted(d.glob("*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            title = str(obj.get("title") or "").strip()
            content = str(obj.get("content") or "").strip()
            if not title or not content:
                continue
            it = {
                "title": title,
                "content": content,
                "url": obj.get("url") or "",
                "tags": list(obj.get("tags") or []),
                "__file": str(p),
            }
            items.append(it)
        except Exception:
            continue
    return items


def _collect_recent_memory(sid: str, limit: int = 5) -> List[Dict[str, Any]]:
    base = ROOT / "subminds" / sid / "memory" / "long_term"
    if not base.exists():
        return []
    items: List[Dict[str, Any]] = []
    files = sorted(base.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    for p in files:
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            title = (obj.get("topic") or obj.get("type") or "Fund").strip()
            content = str(obj.get("content") or "").strip()
            if not content:
                continue
            items.append({"title": title, "content": content, "url": "", "tags": []})
        except Exception:
            continue
    return items


def ingest(base: str, sid: str, key: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not items:
        return {"ok": True, "imported": 0}
    url = base.rstrip("/") + f"/api/subminds/{sid}/ingest"
    payload = {"items": [{k: v for k, v in it.items() if not k.startswith("__")} for it in items]}
    r = requests.post(url, json=payload, headers={"X-Submind-Key": key, "Content-Type": "application/json"}, timeout=20)
    try:
        data = r.json()
    except Exception:
        data = {"ok": False, "status": r.status_code}
    if r.ok and isinstance(data, dict) and data.get("ok"):
        return data
    return {"ok": False, "status": r.status_code, "data": data}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="submind id")
    ap.add_argument("--key", help="api key (plaintext)")
    ap.add_argument("--key-file", help="path to file containing api key")
    ap.add_argument("--base", default=os.getenv("SUBMIND_BASE", "http://127.0.0.1:8000"))
    ap.add_argument("--limit", type=int, default=5, help="max items from memory if no outbox")
    args = ap.parse_args()

    sid = args.id
    key = _load_key(sid, args.key, args.key_file)
    items = _collect_outbox(sid)
    used_outbox = True
    if not items:
        items = _collect_recent_memory(sid, limit=args.limit)
        used_outbox = False

    res = ingest(args.base, sid, key, items)
    if not res.get("ok"):
        print("ingest failed:", res, file=sys.stderr)
        return 1
    print(f"imported {res.get('imported',0)} items")

    if used_outbox and res.get("imported", 0) > 0:
        sent_dir = ROOT / "subminds" / sid / "sent"
        sent_dir.mkdir(parents=True, exist_ok=True)
        for it in items[: res.get("imported", 0)]:
            p = Path(it.get("__file") or "")
            if p.exists():
                ts = int(time.time())
                p.rename(sent_dir / f"{ts}_{p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

