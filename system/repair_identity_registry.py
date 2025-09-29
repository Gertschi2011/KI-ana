#!/usr/bin/env python3
import json, base64, shutil
from pathlib import Path
from datetime import datetime

BASE = Path.home() / "ki_ana"
KEYS = BASE / "system" / "keys"
REG  = KEYS / "identity_registry.json"
OWNER_PUB = KEYS / "owner_public.key"

def b64file(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode()

def backup(path: Path) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    bk = path.with_suffix(path.suffix + f".bak_{ts}")
    shutil.copy2(path, bk)
    return bk

def default_registry(owner_pub: str) -> dict:
    return {
        "owner_pubkey": owner_pub,
        "subminds": [],
        "revoked_keys": []
    }

def main():
    if not OWNER_PUB.exists():
        raise SystemExit(f"Owner-Public-Key fehlt: {OWNER_PUB}")

    owner_b64 = b64file(OWNER_PUB)

    if not REG.exists():
        REG.parent.mkdir(parents=True, exist_ok=True)
        REG.write_text(json.dumps(default_registry(owner_b64), indent=2), encoding="utf-8")
        print("✅ Registry neu erstellt:", REG)
        return

    # vorhandene Registry prüfen
    raw = REG.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except Exception:
        bk = backup(REG)
        REG.write_text(json.dumps(default_registry(owner_b64), indent=2), encoding="utf-8")
        print(f"🩹 Registry war kaputt. Backup: {bk}\n✅ Neu erstellt: {REG}")
        return

    changed = False
    if not isinstance(data, dict):
        bk = backup(REG)
        REG.write_text(json.dumps(default_registry(owner_b64), indent=2), encoding="utf-8")
        print(f"🩹 Registry hatte falsches Format. Backup: {bk}\n✅ Neu erstellt: {REG}")
        return

    if "owner_pubkey" not in data or not data.get("owner_pubkey"):
        data["owner_pubkey"] = owner_b64
        changed = True
    if "subminds" not in data or not isinstance(data.get("subminds"), list):
        data["subminds"] = []
        changed = True
    if "revoked_keys" not in data or not isinstance(data.get("revoked_keys"), list):
        data["revoked_keys"] = []
        changed = True

    if changed:
        bk = backup(REG)
        REG.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"🔧 Registry repariert. Backup: {bk}\n✅ Aktuell: {REG}")
    else:
        print("✅ Registry ist in Ordnung:", REG)

if __name__ == "__main__":
    main()
