import json, hashlib
from pathlib import Path

try:
    from nacl import signing, exceptions, encoding
    HAVE_NACL = True
except ImportError:
    HAVE_NACL = False

CHAIN_DIR = Path.home() / "ki_ana/system/chain"

def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def verify_block(block: dict, prev_hash: str) -> tuple[bool, str]:
    # previous_hash
    if block.get("previous_hash","") != prev_hash:
        return False, "previous_hash mismatch"

    # eigenen hash nachrechnen
    content = {k: block[k] for k in block if k not in ("hash","signature","signer_pubkey")}
    calc_hash = sha256_str(json.dumps(content, sort_keys=True, ensure_ascii=False))
    if calc_hash != block.get("hash"):
        return False, "hash mismatch"

    # Signatur prüfen (falls vorhanden)
    sig = block.get("signature","")
    pk  = block.get("signer_pubkey","")
    if sig and pk:
        if not HAVE_NACL:
            return False, "pynacl not installed but signature present"
        try:
            verify_key = signing.VerifyKey(encoding.Base64Encoder.decode(pk.encode()))
            verify_key.verify(json.dumps(content, sort_keys=True, ensure_ascii=False).encode(),
                              encoding.Base64Encoder.decode(sig.encode()))
        except Exception as e:
            return False, f"signature invalid: {e}"

    return True, "ok"

if __name__ == "__main__":
    blocks = sorted(CHAIN_DIR.glob("block_*.json"), key=lambda p: int(p.stem.split("_")[1]))
    prev = "GENESIS_BLOCK_HASH"
    ok_all = True
    for p in blocks:
        data = json.loads(p.read_text(encoding="utf-8"))
        ok, msg = verify_block(data, prev)
        print(f"{p.name}: {'OK' if ok else 'FAIL'} — {msg}")
        if not ok:
            ok_all = False
            break
        prev = data["hash"]
    print("✅ Chain valid." if ok_all else "❌ Chain invalid.")
