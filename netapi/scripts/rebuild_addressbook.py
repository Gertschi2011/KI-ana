#!/usr/bin/env python3
"""Utility: rebuild addressbook.json from filesystem blocks.
Run from project root: python3 netapi/scripts/rebuild_addressbook.py
"""
from pathlib import Path
import json
from datetime import datetime

from netapi.utils.fs import atomic_write_json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHAIN_DIR = PROJECT_ROOT / "system" / "chain"
MEM_BLOCKS_DIR = PROJECT_ROOT / "memory" / "long_term" / "blocks"
OUT_DIR = PROJECT_ROOT / "memory" / "index"

out = {"blocks": [], "rebuilt_at": datetime.utcnow().isoformat() + "Z"}
for base in (CHAIN_DIR, MEM_BLOCKS_DIR):
    if not base.exists():
        continue
    for p in sorted(base.glob('*.json')):
        try:
            data = json.loads(p.read_text(encoding='utf-8') or '{}')
        except Exception:
            data = {}
        tags = []
        try:
            if isinstance(data.get('tags'), list):
                tags = [str(x) for x in (data.get('tags') or [])]
            elif isinstance((data.get('meta') or {}).get('tags'), list):
                tags = [str(x) for x in ((data.get('meta') or {}).get('tags') or [])]
        except Exception:
            tags = []
        entry = {
            'block_id': data.get('id') or p.stem,
            'path': str(p.relative_to(PROJECT_ROOT).as_posix()),
            'title': data.get('title') or data.get('topic') or '',
            'topic': data.get('topic') or '',
            'timestamp': data.get('timestamp') or data.get('ts') or '',
            'source': data.get('source') or ((data.get('meta') or {}).get('source') or ''),
            'tags': tags,
        }
        out['blocks'].append(entry)

OUT_DIR.mkdir(parents=True, exist_ok=True)
ab_path = OUT_DIR / 'addressbook.json'
atomic_write_json(ab_path, out, kind="index", min_bytes=2)
print(f"Wrote {len(out['blocks'])} entries to {ab_path}")
