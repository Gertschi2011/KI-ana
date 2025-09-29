#!/usr/bin/env python3
from __future__ import annotations
import sys, json, hashlib
from pathlib import Path
from importlib.machinery import SourceFileLoader

BASE_DIR = Path.home() / "ki_ana"
SIGNER_PATH = BASE_DIR / "system" / "block_signer.py"

def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def main():
    if len(sys.argv) < 2:
        print("Usage: sign_block.py <path/to/block.json>")
        sys.exit(2)
    p = Path(sys.argv[1])
    if not p.exists():
        print(f"File not found: {p}")
        sys.exit(2)
    data = json.loads(p.read_text(encoding="utf-8"))
    # ensure canonical_hash (content based) if missing
    meta = data.setdefault("meta", {})
    if not meta.get("canonical_hash"):
        content = str(data.get("content") or "")
        meta["canonical_hash"] = sha256_text(content)
    # sign via system/block_signer
    if not SIGNER_PATH.exists():
        print("block_signer.py not found")
        sys.exit(3)
    signer = SourceFileLoader("block_signer", str(SIGNER_PATH)).load_module()  # type: ignore
    sig, pub, ts = signer.sign_block(data)  # type: ignore
    data["signature"], data["pubkey"], data["signed_at"] = sig, pub, ts
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Signed {p}")

if __name__ == "__main__":
    main()
