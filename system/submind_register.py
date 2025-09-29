#!/usr/bin/env python3
import json, base64, argparse, os
from pathlib import Path

BASE = Path.home() / "ki_ana"
KEYS = BASE / "system" / "keys"
REG  = KEYS / "identity_registry.json"

def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()

def ensure_registry():
    if not REG.exists():
        REG.parent.mkdir(parents=True, exist_ok=True)
        REG.write_text(json.dumps({"owner_pubkey":"","subminds":[],"revoked_keys":[]}, indent=2), encoding="utf-8")
    return json.loads(REG.read_text(encoding="utf-8"))

def save_registry(d):
    REG.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="Submind-ID (z.B. emo-001)")
    ap.add_argument("--roles", default="learner,sensor", help="Komma-separiert")
    ap.add_argument("--trust", type=float, default=0.6)
    ap.add_argument("--owner-signed", action="store_true", help="Markiere, dass der Owner den Eintrag freigibt")
    args = ap.parse_args()

    try:
        from nacl import signing
    except ImportError:
        print("Bitte pynacl im venv installieren.")
        return 1

    # Schlüssel erzeugen
    sk = signing.SigningKey.generate()
    pk = sk.verify_key
    priv_b = sk.encode()
    pub_b  = pk.encode()

    KEYS.mkdir(parents=True, exist_ok=True)
    out_priv = KEYS / f"{args.id}_private.key"
    out_pub  = KEYS / f"{args.id}_public.key"
    out_priv.write_bytes(priv_b)
    out_pub.write_bytes(pub_b)
    os.chmod(out_priv, 0o600)

    # Registry aktualisieren
    reg = ensure_registry()
    reg.setdefault("subminds", [])
    # vorhandenen Eintrag überschreiben/ersetzen
    reg["subminds"] = [s for s in reg["subminds"] if s.get("id") != args.id]
    reg["subminds"].append({
        "id": args.id,
        "pubkey": b64(pub_b),
        "roles": [r.strip() for r in args.roles.split(",") if r.strip()],
        "trust": args.trust,
        "owner_signed": bool(args.owner_signed)
    })
    save_registry(reg)

    print("✅ Submind registriert")
    print("   ID:", args.id)
    print("   Public:", b64(pub_b))
    print("   Private-Key:", out_priv)
    print("   Registry:", REG)

if __name__ == "__main__":
    raise SystemExit(main())
