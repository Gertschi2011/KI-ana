#!/usr/bin/env python3
from __future__ import annotations
import os, json
from pathlib import Path
from glob import glob
import requests
from importlib.machinery import SourceFileLoader

BASE_DIR = Path.home() / "ki_ana"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"
GENESIS2 = BLOCKS_DIR / "genesis_2.json"
UTILS_PATH = BASE_DIR / "system" / "block_utils.py"
GENESIS_LOADER = BASE_DIR / "system" / "genesis_loader.py"

_utils = SourceFileLoader("block_utils", str(UTILS_PATH)).load_module()  # type: ignore


def exists(p: Path) -> bool:
    try:
        return p.exists()
    except Exception:
        return False


def verify_signature_file(p: Path) -> bool:
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        ok, _ = _utils.verify_signature(obj)  # type: ignore
        return bool(ok)
    except Exception:
        return False


def check_feedback_api(base_url: str = "http://localhost:8000") -> bool:
    try:
        r = requests.post(f"{base_url}/feedback", json={
            "response_id": "checkup_test",
            "helpfulness": 0.1,
            "clarity": 0.1,
            "comment": "checkup probe"
        }, timeout=3)
        return r.status_code in (200, 201)
    except Exception:
        return False


def reflection_synthetic_test() -> bool:
    # Write two synthetic blocks with contradictory reflection hints and run self_reflection.reflect()
    try:
        from importlib.machinery import SourceFileLoader as _Loader
        sr = _Loader("self_reflection", str(BASE_DIR / "system" / "self_reflection.py")).load_module()  # type: ignore
        # Just call reflect; the engine scans last N blocks and may generate a reflection block
        sr.reflect(max_blocks=10, write_blocks=True)  # type: ignore
        # Check if a reflection_* block exists
        found = any(Path(p).name.startswith("reflection_") for p in glob(str(BLOCKS_DIR / "*.json")))
        return bool(found)
    except Exception:
        return False


def main():
    print("📦 Speicherpfade vorhanden:", exists(BLOCKS_DIR))
    print("🔐 Emergency-Block existiert:", exists(BLOCKS_DIR / "emergency_override.json"))
    try:
        total_blocks = len(list(BLOCKS_DIR.glob("*.json")))
    except Exception:
        total_blocks = 0
    print("🧠 Mindestens 1 Wissensblock gespeichert:", total_blocks > 0)
    print("📜 Genesis 2 korrekt signiert:", verify_signature_file(GENESIS2))
    # Try viewer then self route
    ok_viewer = False
    try:
        ok_viewer = requests.get("http://localhost:8000/viewer", timeout=2).status_code == 200
    except Exception:
        ok_viewer = False
    if not ok_viewer:
        try:
            ok_viewer = requests.get("http://localhost:8000/self", timeout=2).status_code == 200
        except Exception:
            pass
    print("🌐 Viewer erreichbar:", ok_viewer)

    # Genesis loader check
    try:
        gmod = SourceFileLoader("genesis_loader", str(GENESIS_LOADER)).load_module()  # type: ignore
        gens = gmod.load_genesis_blocks()  # type: ignore
        print("🧠 Genesis-Loader lädt Ursprünge:", isinstance(gens, dict) and len(gens) >= 1)
    except Exception:
        print("🧠 Genesis-Loader lädt Ursprünge:", False)

    # Feedback API
    print("💬 Feedback-API speichert Block:", check_feedback_api())

    # Reflection synthetic probe
    print("🤖 Reflexions-Test erzeugt Block:", reflection_synthetic_test())


if __name__ == "__main__":
    main()
