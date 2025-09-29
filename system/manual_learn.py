import os
import json
import hashlib
from datetime import datetime
from pathlib import Path

# Faktenbeispiel
fact = "Die Erde ist etwa 4,54 Milliarden Jahre alt."
sources = [
    "https://de.wikipedia.org/wiki/Alter_der_Erde",
    "https://www.geo.de/wissen/20846-rtkl-wie-alt-ist-die-erde",
    "https://www.nationalgeographic.de/wissenschaft/2019/02/wie-wissenschaftler-das-alter-der-erde-bestimmen"
]
trust_level = 0.9
topic = "Geschichte"
verzeichnis_eintrag = f"Fact: {fact[:30]}..., Sources: {len(sources)}, Trust: {trust_level}"

# Block vorbereiten
block = {
    "block_type": "knowledge_entry",
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "fact": fact,
    "sources": sources,
    "trust_level": trust_level,
    "validated_by_subminds": True,
    "topic": topic,
    "memory_destination": "long_term"
}

# Hash erzeugen
block_json = json.dumps(block, indent=2)
block_hash = hashlib.sha256(block_json.encode()).hexdigest()

# Speicherorte
memory_dir = Path.home() / "ki_ana" / "memory" / "long_term"
memory_dir.mkdir(parents=True, exist_ok=True)

block_file = memory_dir / f"{block_hash}.json"
block_file.write_text(block_json)

# Themenverzeichnis aktualisieren
index_file = Path.home() / "ki_ana" / "system" / "learning_engine.json"
with open(index_file, "r") as f:
    index_data = json.load(f)

if topic in index_data["topic_index"]:
    index_data["topic_index"][topic].append({
        "hash": block_hash,
        "summary": verzeichnis_eintrag
    })

# Themenverzeichnis speichern
with open(index_file, "w") as f:
    json.dump(index_data, f, indent=2)

print(f"Faktenblock gespeichert: {block_file}")
print(f"SHA256 Hash: {block_hash}")

# ⬇️ Reflexionsmodul laden und starten
import subprocess
subprocess.run(["python3", os.path.expanduser("~/ki_ana/learning/brain_modules/self_reflection.py")])
