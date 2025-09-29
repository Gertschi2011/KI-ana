#!/usr/bin/env python3
import os, re, json, time, hashlib, subprocess
from pathlib import Path
from datetime import datetime

BASE = Path.cwd()  # Laufzeitverzeichnis des Submind
MEM  = BASE / "memory"
LT   = MEM / "long_term"
OUTBOX = BASE / "outbox"
CFG  = BASE / "config.json"

MEM.mkdir(parents=True, exist_ok=True)
LT.mkdir(parents=True, exist_ok=True)
OUTBOX.mkdir(parents=True, exist_ok=True)
if not CFG.exists():
    CFG.write_text(json.dumps({
        "submind_id": "unknown",
        "parent_endpoint": "",
        "parent_pubkey": "",
        "policies": {
            "allow_domains": ["de.wikipedia.org","wikipedia.org","britannica.com"],
            "timeout_sec": 15
        }
    }, indent=2), encoding="utf-8")

def now_iso(): return datetime.utcnow().isoformat()+"Z"

def save_fact(topic: str, content: str, source="User/Erklärung"):
    ts = now_iso()
    blk = {"type":"manual_fact","topic":topic,"content":content,"timestamp":ts,"source":source}
    b = json.dumps(blk, ensure_ascii=False, indent=2).encode()
    h = hashlib.sha256(b).hexdigest()
    out = LT / f"{h}.json"
    out.write_bytes(b)
    print("💾 gespeichert:", out)
    # Outbox-Eintrag für Ingest vorbereiten
    try:
        outbox_item = {
            "title": topic or "Fakt",
            "content": content,
            "url": "",
            "tags": ["manual"],
        }
        (OUTBOX / f"{h}.json").write_text(json.dumps(outbox_item, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return out

def main():
    print("🤖 Submind Listener aktiv. Schreibe 'STOPP' zum Beenden.")
    while True:
        try:
            s = input("👤 Sag mir was: ").strip()
            if s.lower() == "stopp": 
                print("👋 tschüss"); break
            if re.search(r'https?://\S+', s):
                # Minimal: lokal speichern als „Quelle“, ohne Hauptcrawler
                save_fact("link", s, "User/Link")
                continue
            if len(s) >= 20 and "?" not in s:
                topic = " ".join(s.lower().split()[:4])
                save_fact(topic, s)
                continue
            print("🙂 Ich brauche eine kurze Erklärung (≥20 Zeichen) oder einen Link.")
        except KeyboardInterrupt:
            print("\n🛑 beendet"); break

if __name__ == "__main__":
    main()
