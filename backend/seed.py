from __future__ import annotations
import os, json, time
from backend.routes.memory import _CHAIN, _hash_block

GENESIS_CONTENT = {
    "title": "KI_ana Genesis",
    "ethics_ref": "GENESIS_ETHICS.md",
    "created": int(time.time()),
}

def run():
    if not _CHAIN:
        b = {"ts": int(time.time()), "type": "GENESIS", "source": "seed", "tags": ["genesis"], "prev_hash": "0"*64, "content": GENESIS_CONTENT}
        b["hash"] = _hash_block(b)
        _CHAIN.append(b)
        print("[seed] genesis block appended")
    print("[seed] users: admin@example.com / admin123 (in-memory)")

if __name__ == "__main__":
    run()
