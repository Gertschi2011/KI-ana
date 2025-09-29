import os
import json
import hashlib
from datetime import datetime

SOURCE_DIR = os.path.expanduser("~/ki_ana/memory/long_term")
CHAIN_DIR = os.path.expanduser("~/ki_ana/system/chain")

def sha256_str(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def block_hash(block_data):
    block_copy = dict(block_data)
    block_copy.pop("hash", None)
    return sha256_str(json.dumps(block_copy, sort_keys=True))

def migrate_blocks():
    if not os.path.exists(CHAIN_DIR):
        os.makedirs(CHAIN_DIR)

    files = sorted(os.listdir(SOURCE_DIR))
    previous_hash = "GENESIS_BLOCK_HASH"  # kann auch Hash vom echten Genesis sein
    block_id = 1

    for filename in files:
        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(SOURCE_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = json.load(f)

        block = {
            "block_id": block_id,
            "type": "knowledge",
            "timestamp": content.get("timestamp", datetime.utcnow().isoformat()),
            "source": content.get("source", "🗂️ Unbekannt"),
            "content": content.get("content", ""),
            "previous_hash": previous_hash,
        }

        block["hash"] = block_hash(block)

        out_path = os.path.join(CHAIN_DIR, f"block_{block_id}.json")
        with open(out_path, "w", encoding="utf-8") as out:
            json.dump(block, out, indent=2, ensure_ascii=False)

        print(f"✅ Block {block_id} gespeichert: {out_path}")
        previous_hash = block["hash"]
        block_id += 1

if __name__ == "__main__":
    migrate_blocks()
