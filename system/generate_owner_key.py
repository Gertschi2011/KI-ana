from pathlib import Path
import json, os
from nacl import signing, encoding

BASE = Path.home() / "ki_ana/system/keys"
REG  = Path.home() / "ki_ana/system/keys/identity_registry.json"
PRIV = BASE / "owner_private.key"
PUB  = BASE / "owner_public.key"

BASE.mkdir(parents=True, exist_ok=True)

# keypair erzeugen
sk = signing.SigningKey.generate()
vk = sk.verify_key

# speichern (privat mit 600!)
PRIV.write_bytes(sk.encode())
os.chmod(PRIV, 0o600)
PUB.write_bytes(vk.encode())

owner_pub_b64 = vk.encode(encoder=encoding.Base64Encoder).decode()
owner_pub_hex = vk.encode(encoder=encoding.HexEncoder).decode()

# registry aktualisieren/ersetzen owner_pubkey
reg = {"owner_pubkey": owner_pub_b64, "subminds": [], "revoked_keys": []}
if REG.exists():
    try:
        old = json.loads(REG.read_text(encoding="utf-8"))
        old["owner_pubkey"] = owner_pub_b64
        reg = old
    except Exception:
        pass
REG.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")

print("✅ Owner-Key erzeugt.")
print(f"🔑 Private: {PRIV}")
print(f"🔐 Public (Base64): {owner_pub_b64}")
print(f"🧩 Public (Hex): {owner_pub_hex}")
