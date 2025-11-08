#!/usr/bin/env python3
"""
Backfill Addressbook from existing memory blocks (non-destructive, idempotent).

Usage:
  python -m netapi.scripts.backfill_addressbook_from_memory [--limit N] [--dry-run]

Notes:
- Reads blocks from memory/long_term/blocks (JSON files) via memory_store index.
- Derives topic via addressbook.extract_topic_from_message(title or first content line).
- Builds topic paths via addressbook.build_topic_paths and registers block in addressbook.
- Idempotent: register_block_for_topic appends only if missing.
- Logs progress every 100 items.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# Project root paths
ROOT = Path(__file__).resolve().parents[2]
MEM_DIR = ROOT / "memory" / "long_term" / "blocks"

# Import helpers
from netapi.core.addressbook import (
    extract_topic_from_message,
    build_topic_paths,
    register_block_for_topic,
)


def _iter_block_files(limit: int | None = None) -> List[Path]:
    files = list(MEM_DIR.rglob("*.json"))
    return files[:limit] if limit else files


def _infer_topic_from_block(obj: Dict[str, Any]) -> str:
    # Prefer explicit fields
    topic = str(obj.get("topic") or obj.get("title") or "").strip()
    if not topic:
        # Fallback: first non-empty line of content
        content = str(obj.get("content") or obj.get("summary") or "").strip()
        first_line = next((ln.strip() for ln in content.splitlines() if ln.strip()), "")
        topic = first_line[:80]
    topic = topic.strip()
    if not topic:
        return ""
    return extract_topic_from_message(topic) or topic


def backfill(limit: int | None = None, dry_run: bool = False) -> Dict[str, int]:
    files = _iter_block_files(limit)
    total = 0
    mapped = 0
    skipped = 0
    for i, fp in enumerate(files, 1):
        total += 1
        try:
            obj = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            skipped += 1
            continue
        block_id = str(obj.get("id") or fp.stem)
        topic = _infer_topic_from_block(obj)
        if not topic:
            skipped += 1
            continue
        paths = build_topic_paths(topic, obj.get("title") or obj.get("content") or "")
        if not paths:
            skipped += 1
            continue
        if dry_run:
            mapped += 1
        else:
            for p in paths:
                try:
                    register_block_for_topic(p, block_id)
                except Exception:
                    # continue mapping other paths
                    pass
            mapped += 1
        if i % 100 == 0:
            print(f"[backfill] processed={i} mapped={mapped} skipped={skipped}")
    print(f"[backfill] done total={total} M={mapped} S={skipped}")
    return {"total": total, "mapped": mapped, "skipped": skipped}


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Limit number of blocks to process")
    ap.add_argument("--dry-run", action="store_true", help="Don't write to addressbook; just simulate")
    args = ap.parse_args(argv)
    limit = args.limit if args.limit and args.limit > 0 else None
    res = backfill(limit=limit, dry_run=args.dry_run)
    print(json.dumps({"ok": True, **res}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
