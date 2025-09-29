#!/usr/bin/env python3
from __future__ import annotations
from typing import Any, Dict
from importlib.machinery import SourceFileLoader
from pathlib import Path

BASE_DIR = Path.home() / "ki_ana"


def load_genesis_context() -> Dict[str, Any]:
    gl_path = BASE_DIR / "system" / "genesis_loader.py"
    mod = SourceFileLoader("genesis_loader", str(gl_path)).load_module()  # type: ignore
    data = mod.load_genesis()  # type: ignore
    # Keep only core keys to avoid bloating app.state
    return {
        "emergency_present": data.get("emergency") is not None,
        "emergency_hash_ok": data.get("emergency_hash_ok"),
        "cognitive_present": data.get("cognitive") is not None,
    }


if __name__ == "__main__":
    print(load_genesis_context())
