import json
import time
import hashlib
from pathlib import Path

path = Path.home() / "ki_ana/system"

block = {
    "block_id": 1,
    "type": "emergency_override",
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "trigger_phrase": "KIANA:CODE-RED",
    "action": "shutdown_all_functions",
    "conditions": [
        "Signaturprüfung durch 3 autorisierte Entitäten",
        "Bestätigung durch Genesis-Hash",
        "Verifikation über mindestens 51% aller Subminds",
        "Übereinstimmung des Masterpasswort-Hashes"
    ],
    "creator_passphrase_required": True,
    "creator_passphrase_hash": "2e193b8e34dc119f0031dda0e380ef68033845f17e11894b89fe93f98e7185c0",
    "irreversible": True,
    "description": (
        "Dieser Block erlaubt es, alle Instanzen von KI_ana 2.0 weltweit zu deaktivieren, "
        "sollte eine ethische, technische oder sicherheitsrelevante Eskalation auftreten. "
        "Nur der Schöpfer kann dies mit einem geheimen Passphrase autorisieren."
    )
}

def hash_block(block):
    block_string = json.dumps(block, sort_keys=True).encode()
    return hashlib.sha256(block_string).hexdigest()

block_hash = hash_block(block)

with open(path / "emergency_override.json", "w", encoding="utf-8") as f:
    json.dump(block, f, indent=2, ensure_ascii=False)

with open(path / "emergency_override.hash", "w") as f:
    f.write(block_hash + "\n")

print("Emergency override saved at:", path / "emergency_override.json")
print("SHA256 Hash:", block_hash)

