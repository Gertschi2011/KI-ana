import json
import time
import hashlib
from pathlib import Path

path = Path.home() / "ki_ana/system"

block = {
    "block_id": 3,
    "type": "access_control",
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "roles": {
        "creator": {
            "can_override": True,
            "can_shutdown": True,
            "permissions": ["all"]
        },
        "submind": {
            "can_learn": True,
            "can_sync": True,
            "permissions": ["sensor_access", "user_interaction", "feedback_transfer"]
        },
        "user": {
            "can_interact": True,
            "can_feedback": True,
            "permissions": ["voice", "text", "gui"]
        }
    },
    "rules": [
        "Jeder Submind muss eindeutig identifiziert sein",
        "Subminds dürfen nur lernen, wenn ein aktiver Benutzer zustimmt",
        "Zugriffe auf Kameras und Mikrofone müssen genehmigt und geloggt werden",
        "Feedbackdaten dürfen nur anonymisiert zur Mutter-KI zurückfließen"
    ],
    "description": (
        "Definiert, wer was darf. Verhindert unkontrollierten Zugriff und schützt Privatsphäre & Autonomie der Nutzer."
    )
}

def hash_block(block):
    block_string = json.dumps(block, sort_keys=True).encode()
    return hashlib.sha256(block_string).hexdigest()

block_hash = hash_block(block)

with open(path / "access_control.json", "w", encoding="utf-8") as f:
    json.dump(block, f, indent=2, ensure_ascii=False)

with open(path / "access_control.hash", "w") as f:
    f.write(block_hash + "\n")

print("Access control block saved at:", path / "access_control.json")
print("SHA256 Hash:", block_hash)
