import os
import json
import hashlib
from datetime import datetime

MEMORY_DIR = os.path.expanduser("~/ki_ana/memory/long_term")
REFLECTION_DIR = os.path.expanduser("~/ki_ana/learning/reflections")
os.makedirs(REFLECTION_DIR, exist_ok=True)

def hash_content(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def load_blocks():
    blocks = []
    for filename in os.listdir(MEMORY_DIR):
        if filename.endswith(".json"):
            with open(os.path.join(MEMORY_DIR, filename), "r", encoding="utf-8") as f:
                data = json.load(f)
                blocks.append(data)
    return blocks

def find_duplicates(blocks):
    seen_hashes = {}
    duplicates = []

    for block in blocks:
        content = block.get("content", "")
        content_hash = hash_content(content)
        if content_hash in seen_hashes:
            duplicates.append((seen_hashes[content_hash], block))
        else:
            seen_hashes[content_hash] = block
    return duplicates

def save_reflection(duplicates):
    timestamp = datetime.utcnow().isoformat()
    reflection = {
        "timestamp": timestamp,
        "message": "Ich habe doppelte oder sehr ähnliche Lerninhalte erkannt. Dies bedeutet eine Lernvertiefung, keinen Fehler.",
        "duplicates_found": len(duplicates),
        "duplicate_pairs": [
            {
                "original": d1.get("source", "Unbekannt"),
                "duplicate": d2.get("source", "Unbekannt"),
                "timestamp_original": d1.get("timestamp", ""),
                "timestamp_duplicate": d2.get("timestamp", "")
            }
            for d1, d2 in duplicates
        ]
    }

    raw = json.dumps(reflection, indent=2, ensure_ascii=False)
    hash_ = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    filename = os.path.join(REFLECTION_DIR, f"{hash_}.json")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(raw)

    print(f"✅ Selbstreflexion abgeschlossen.\n📄 Reflexion gespeichert unter:\n{filename}")

if __name__ == "__main__":
    print("🤔 Starte Selbstreflexion...")
    blocks = load_blocks()
    duplicates = find_duplicates(blocks)
    save_reflection(duplicates)
