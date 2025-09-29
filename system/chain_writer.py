import os, json, hashlib
from pathlib import Path
from datetime import datetime

try:
    from nacl import signing, encoding
except ImportError:
    signing = None

CHAIN_DIR = Path.home() / "ki_ana/system/chain"
KEYS_DIR  = Path.home() / "ki_ana/system/keys"
OWNER_PRIV= KEYS_DIR / "owner_private.key"
REGISTRY  = KEYS_DIR / "identity_registry.json"

def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def load_last_block():
    CHAIN_DIR.mkdir(parents=True, exist_ok=True)
    blocks = sorted(CHAIN_DIR.glob("block_*.json"), key=lambda p: int(p.stem.split("_")[1]))
    if not blocks:
        return None, "GENESIS_BLOCK_HASH", 0
    last = blocks[-1]
    data = json.loads(last.read_text(encoding="utf-8"))
    return data, data.get("hash",""), int(data.get("block_id",0))

def sign_bytes(b: bytes) -> str | None:
    if signing is None or not OWNER_PRIV.exists():
        return None
    sk = signing.SigningKey(OWNER_PRIV.read_bytes())
    sig = sk.sign(b).signature
    return encoding.Base64Encoder.encode(sig).decode()

def write_chain_block(payload: dict) -> Path:
    _, prev_hash, last_id = load_last_block()

    block = {
        "block_id": last_id + 1,
        "timestamp": datetime.utcnow().isoformat()+"Z",
        "previous_hash": prev_hash,
        "type": payload.get("type","knowledge"),
        "topic": payload.get("topic"),
        "source": payload.get("source"),
        "memory_path": payload.get("memory_path"),
        "content_hash": payload.get("content_hash"),
        "meta": payload.get("meta", {}),
    }

    # Hash über den inhaltlichen Block (ohne hash/signature/signer_pubkey)
    to_hash = json.dumps(block, sort_keys=True, ensure_ascii=False)
    block_hash = sha256_str(to_hash)
    block["hash"] = block_hash

    # optional signieren (falls Key vorhanden)
    signature = sign_bytes(to_hash.encode("utf-8"))
    if signature:
        # Public Key aus Registry beilegen
        try:
            reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
            block["signer_pubkey"] = reg.get("owner_pubkey", "")
        except Exception:
            block["signer_pubkey"] = ""
        block["signature"] = signature
    else:
        block["signer_pubkey"] = ""
        block["signature"] = ""

    out = CHAIN_DIR / f"block_{block['block_id']}.json"
    out.write_text(json.dumps(block, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Chain-Block gespeichert: {out}")
    print(f"🔗 Hash: {block['hash']}")
    if signature:
        print("✍️  Signatur: vorhanden")
    else:
        print("ℹ️  Keine Signatur (kein Key gefunden oder pynacl nicht installiert).")
    return out

if __name__ == "__main__":
    import argparse, hashlib
    ap = argparse.ArgumentParser(description="Schreibe einen neuen Verkettungsblock (signiert, wenn Key vorhanden).")
    ap.add_argument("--type", required=True)
    ap.add_argument("--topic", default="")
    ap.add_argument("--source", default="")
    ap.add_argument("--memory_path", required=True)
    ap.add_argument("--meta", default="{}")
    args = ap.parse_args()

    mem_path = Path(args.memory_path)
    if not mem_path.exists():
        raise SystemExit(f"❌ memory_path nicht gefunden: {mem_path}")

    content_hash = hashlib.sha256(mem_path.read_bytes()).hexdigest()
    try:
        meta = json.loads(args.meta)
    except Exception:
        meta = {}

    payload = {
        "type": args.type,
        "topic": args.topic or "",
        "source": args.source or "",
        "memory_path": str(mem_path),
        "content_hash": content_hash,
        "meta": meta,
    }
    write_chain_block(payload)
