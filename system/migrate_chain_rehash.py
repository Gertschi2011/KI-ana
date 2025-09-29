import json, hashlib, shutil
from pathlib import Path
from datetime import datetime

from nacl import signing, encoding

CHAIN_DIR = Path.home() / "ki_ana/system/chain"
OUT_DIR   = Path.home() / "ki_ana/system/chain_migrated"
KEY_PRIV  = Path.home() / "ki_ana/system/keys/owner_private.key"
REG_PATH  = Path.home() / "ki_ana/system/keys/identity_registry.json"

def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def load_blocks():
    blocks = sorted(CHAIN_DIR.glob("block_*.json"), key=lambda p: int(p.stem.split("_")[1]))
    items = []
    for p in blocks:
        try:
            items.append((p, json.loads(p.read_text(encoding="utf-8"))))
        except Exception as e:
            print(f"⚠️ Überspringe {p.name}: {e}")
    return items

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Key laden
    sk = signing.SigningKey(KEY_PRIV.read_bytes())
    vk_b64 = json.loads(REG_PATH.read_text(encoding="utf-8")).get("owner_pubkey","")

    prev_hash = "GENESIS_BLOCK_HASH"
    new_id = 0

    for p, data in load_blocks():
        # Neuen Blockkörper bauen (vereinheitlicht)
        body = {
            "block_id": new_id + 1,
            "timestamp": data.get("timestamp") or datetime.utcnow().isoformat()+"Z",
            "previous_hash": prev_hash,
            "type": data.get("type","knowledge"),
            "topic": data.get("topic",""),
            "source": data.get("source",""),
            "memory_path": data.get("memory_path",""),
            "content_hash": data.get("content_hash",""),
            "meta": data.get("meta", {}),
        }

        # Hash berechnen (ohne hash/signature/signer_pubkey)
        to_hash = json.dumps(body, sort_keys=True, ensure_ascii=False)
        body["hash"] = sha256_str(to_hash)

        # Signieren
        sig = sk.sign(to_hash.encode("utf-8")).signature
        body["signer_pubkey"] = vk_b64
        body["signature"] = encoding.Base64Encoder.encode(sig).decode()

        # Schreiben
        outp = OUT_DIR / f"block_{body['block_id']}.json"
        outp.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")

        # für nächsten Block
        prev_hash = body["hash"]
        new_id += 1

        print(f"✅ migriert: {outp.name}")

    print("🎉 Migration fertig:", OUT_DIR)

if __name__ == "__main__":
    main()
