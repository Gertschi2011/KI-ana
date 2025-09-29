import os
import json
import hashlib
from datetime import datetime

CHAIN_DIR = os.path.expanduser("~/ki_ana/system/chain")

def load_blocks():
    blocks = []
    for filename in sorted(os.listdir(CHAIN_DIR)):
        if filename.startswith("block_") and filename.endswith(".json"):
            path = os.path.join(CHAIN_DIR, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    block = json.load(f)
                    blocks.append((filename, block))
            except Exception as e:
                print(f"❌ Fehler beim Laden von {filename}: {e}")
    return blocks

def hash_block(block):
    block_copy = block.copy()
    block_copy.pop("hash", None)
    block_serialized = json.dumps(block_copy, sort_keys=True).encode("utf-8")
    return hashlib.sha256(block_serialized).hexdigest()

def display_chain():
    print("🧠 KI_ana Blockchain-Viewer")
    print("="*35)
    blocks = load_blocks()

    for filename, block in blocks:
        print(f"\n🧱 {filename}")
        ts = block.get("timestamp", "Unbekannt")
        source = block.get("source", "Manuell")
        print(f"🕒 {ts}")
        print(f"🌐 Quelle: {source}")
        prev = block.get("previous_hash", "GENESIS")
        print(f"🔗 Vorheriger Hash: {prev}")
        actual_hash = block.get("hash", "")
        calc_hash = hash_block(block)
        if actual_hash == calc_hash:
            print("✅ Integrität: OK")
        else:
            print("❌ Integrität: FEHLER")
        print("-" * 35)

if __name__ == "__main__":
    display_chain()
