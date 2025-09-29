#!/usr/bin/env python3
from __future__ import annotations
"""
Submind Outbox‑Pusher

Reads JSON files from ./outbox and pushes them to the parent via
  POST {parent_base}/api/subminds/{submind_id}/ingest

Auth:
- Reads plaintext key from env SUBMIND_KEY or config.json['api_key']
- Otherwise, uses Bearer from env SUBMIND_BEARER

Retry:
- Simple retry with exponential backoff on network errors
"""
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, List

import requests

BASE = Path.cwd()
CFG  = BASE / "config.json"
OUTBOX = BASE / "outbox"
DONE   = BASE / "outbox.sent"

OUTBOX.mkdir(parents=True, exist_ok=True)
DONE.mkdir(parents=True, exist_ok=True)


def load_cfg() -> Dict[str, Any]:
    try:
        return json.loads(CFG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def pick_auth(cfg: Dict[str, Any]) -> Dict[str, str]:
    key = os.getenv("SUBMIND_KEY") or cfg.get("api_key") or ""
    if key:
        return {"X-Submind-Key": key}
    bearer = os.getenv("SUBMIND_BEARER") or ""
    if bearer:
        return {"Authorization": f"Bearer {bearer}"}
    return {}


def parent_base(cfg: Dict[str, Any]) -> str:
    base = cfg.get("parent_base") or os.getenv("PARENT_BASE") or "http://localhost:8000"
    return str(base).rstrip("/")


def run_once() -> int:
    cfg = load_cfg()
    sid = (cfg.get("submind_id") or "").strip()
    if not sid:
        print("missing submind_id in config.json"); return 2
    headers = {"Content-Type": "application/json"}
    headers.update(pick_auth(cfg))
    base = parent_base(cfg)

    # Collect items
    items: List[Dict[str, Any]] = []
    files: List[Path] = []
    for p in sorted(OUTBOX.glob("*.json")):
        try:
            it = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(it, dict) and it.get("content"):
                items.append({
                    "title": str(it.get("title") or "Item"),
                    "content": str(it.get("content") or ""),
                    "url": str(it.get("url") or ""),
                    "tags": list(it.get("tags") or []),
                })
                files.append(p)
        except Exception:
            continue
    if not items:
        return 0

    payload = {"items": items}
    url = f"{base}/api/subminds/{sid}/ingest"
    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
        if r.status_code >= 400:
            print("push failed:", r.status_code, r.text[:200])
            return 1
        data = r.json()
        if not data or not data.get("ok"):
            print("push error:", data)
            return 1
        # move to sent
        for p in files:
            p.rename(DONE / p.name)
        return 0
    except Exception as e:
        print("push exception:", e)
        return 1


def main():
    # Simple loop with backoff
    backoff = 2
    while True:
        rc = run_once()
        if rc == 0:
            backoff = 2
        time.sleep(backoff)
        backoff = min(60, backoff * 2) if rc else 2


if __name__ == "__main__":
    main()

