import json
import hashlib
from datetime import datetime
from pathlib import Path

# Pfad zur Datei
block_path = Path.home() / "ki_ana" / "system" / "learning_engine.json"

# Inhalt des Blocks
block_content = {
    "block_id": 4,
    "block_type": "learning_engine",
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "description": "Definiert das initiale Lernsystem von KI_ana 2.0, inklusive Speicherstruktur, Lernregeln und Themenverzeichnis.",
    "memory_structure": {
        "short_term": "~/ki_ana/memory/short_term/",
        "long_term": "~/ki_ana/memory/long_term/",
        "archive": "~/ki_ana/memory/archive/",
        "trash": "~/ki_ana/memory/trash/"
    },
    "learning_rules": {
        "min_sources": 3,
        "required_trust_level": 0.75,
        "submind_validation": True
    },
    "topic_index": {
        "Geschichte": [],
        "Mathematik": [],
        "Ethik": [],
        "Technologie": [],
        "Ökologie": [],
        "Kommunikation": []
    },
    "forgetting_rules": {
        "inconsistent_info": "move_to_trash",
        "obsolete_or_proven_false": "archive_then_purge"
    }
}

# Hash berechnen
block_json = json.dumps(block_content, indent=2)
block_hash = hashlib.sha256(block_json.encode()).hexdigest()

# Datei speichern
block_path.write_text(block_json)
print(f"Learning engine block saved at: {block_path}")
print(f"SHA256 Hash: {block_hash}")
