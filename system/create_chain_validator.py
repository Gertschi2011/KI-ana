import json
import time
import hashlib
from pathlib import Path

path = Path.home() / "ki_ana/system"

block = {
    "block_id": 2,
    "type": "chain_validator",
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "checks": [
        "Integrität von Block 0 (genesis_block.json)",
        "Integrität von Block 1 (emergency_override.json)",
        "Existenz und Unveränderlichkeit aller vorangegangenen Systemblöcke",
        "Keine rückwirkenden Änderungen erlaubt"
    ],
    "validation_interval": "12h",
    "enforcement": "lockdown_if_invalid",
    "description": (
        "Dieser Block definiert die Selbstüberprüfung der Kettenintegrität. "
        "Bei Feststellung von Manipulationen wird KI_ana 2.0 sofort in den Sicherheitsmodus versetzt."
    )
}

def hash_block(block):
    block_string = json.dumps(block, sort_keys=True).encode()
    return hashlib.sha256(block_string).hexdigest()

block_hash = hash_block(block)

with open(path / "chain_validator.json", "w", encoding="utf-8") as f:
    json.dump(block, f, indent=2, ensure_ascii=False)

with open(path / "chain_validator.hash", "w") as f:
    f.write(block_hash + "\n")

print("Chain validator saved at:", path / "chain_validator.json")
print("SHA256 Hash:", block_hash)
