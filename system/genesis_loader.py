#!/usr/bin/env python3
from __future__ import annotations
import json, hashlib
from typing import Any, Dict, List
from pathlib import Path

BASE_DIR = Path.home() / "ki_ana"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"

EMERGENCY_EXPECTED_SHA256 = "2e193b8e34dc119f0031dda0e380ef68033845f17e11894b89fe93f98e7185c0"


def _sha256_bytes(b: bytes) -> str:
    import hashlib as _h
    return _h.sha256(b).hexdigest()


def load_genesis() -> Dict[str, Any]:
    """Load all genesis-like blocks. Returns dict with keys: emergency, cognitive, others.
    A block qualifies if id starts with 'genesis' or tags include 'genesis'.
    """
    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    emergency = None
    cognitive = None
    others: List[Dict[str, Any]] = []
    for p in BLOCKS_DIR.glob("*.json"):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        tags = [t.lower() for t in (b.get("tags") or [])]
        is_gen = (str(b.get("id") or "").lower().startswith("genesis") or ("genesis" in tags))
        if not is_gen:
            continue
        # classify
        tid = (b.get("id") or "").lower()
        if "emergency" in tid or "override" in tid:
            emergency = b
        elif tid in {"genesis_2", "genesis2", "cognitive_origin"} or "cognitive_origin" in tags:
            cognitive = b
        else:
            others.append(b)
    # verify emergency sha256 if present
    emergency_ok = None
    if emergency is not None:
        try:
            body = json.dumps(emergency, ensure_ascii=False, sort_keys=True).encode("utf-8")
            emergency_ok = (_sha256_bytes(body) == EMERGENCY_EXPECTED_SHA256)
        except Exception:
            emergency_ok = False
    return {
        "emergency": emergency,
        "emergency_hash_ok": emergency_ok,
        "cognitive": cognitive,
        "others": others,
    }


if __name__ == "__main__":
    data = load_genesis()
    print(json.dumps(data, ensure_ascii=False, indent=2))
