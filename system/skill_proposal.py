#!/usr/bin/env python3
import argparse, json, hashlib, base64, os, re
from pathlib import Path
from datetime import datetime

BASE   = Path.home() / "ki_ana"
SKILLS = BASE / "skills"
PROP   = SKILLS / "proposals"
KEYS   = BASE / "system" / "keys"
OWNER_PRIV = KEYS / "owner_private.key"

def now(): return datetime.utcnow().isoformat()+"Z"

def sha256_bytes(b: bytes) -> str:
    import hashlib
    return hashlib.sha256(b).hexdigest()

def sign(data_b: bytes) -> str:
    try:
        from nacl import signing
    except ImportError:
        raise SystemExit("pynacl fehlt (im venv installieren).")
    sk = signing.SigningKey(OWNER_PRIV.read_bytes())
    sig = sk.sign(data_b).signature
    return base64.b64encode(sig).decode()

def verify(data_b: bytes, sig_b64: str, pubkey_b64: str) -> bool:
    from nacl import signing, exceptions
    vk = signing.VerifyKey(base64.b64decode(pubkey_b64))
    try:
        vk.verify(data_b, base64.b64decode(sig_b64))
        return True
    except Exception:
        return False

def create(args):
    PROP.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": args.id,
        "name": args.name,
        "version": args.version,
        "author": "ki_ana",
        "created_utc": now(),
        "permissions": [p.strip() for p in args.permissions.split(",") if p.strip()],
        "risk": {"notes": args.risk or "", "mitigations": args.mitigations or ""},
        "status": "proposed",   # proposed|tested|approved|rejected|deployed
        "sandbox": {"ok": False, "note": ""},
        "freigabe": {"owner_signed": False, "submind_quorum": "0/0"},
        "files": {
            "staging_path": str((SKILLS / "staging" / args.id).resolve()),
            "entry": "skill.py",
            "manifest": "manifest.json"
        }
    }
    out = PROP / f"{args.id}.proposal.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print("✅ Proposal erstellt:", out)

def sign_proposal(args):
    p = PROP / f"{args.id}.proposal.json"
    if not p.exists(): raise SystemExit("Proposal nicht gefunden.")
    d = json.loads(p.read_text(encoding="utf-8"))
    raw = json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")
    d["signature"] = {
        "proposal_sha256": sha256_bytes(raw),
        "owner_sig_b64": sign(raw)
    }
    d["freigabe"]["owner_signed"] = True
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    print("✍️  Proposal signiert.")

def status(args):
    p = PROP / f"{args.id}.proposal.json"
    if not p.exists(): raise SystemExit("Proposal nicht gefunden.")
    print(p.read_text(encoding="utf-8"))

def update_status(id_: str, **kv):
    p = PROP / f"{id_}.proposal.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    for k,v in kv.items():
        # einfache, flache updates:
        d[k] = v
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--id", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--version", default="0.1")
    c.add_argument("--permissions", default="read_memory,write_memory")
    c.add_argument("--risk", default="")
    c.add_argument("--mitigations", default="")

    s = sub.add_parser("sign")
    s.add_argument("--id", required=True)

    st = sub.add_parser("status")
    st.add_argument("--id", required=True)

    args = ap.parse_args()
    if args.cmd == "create": create(args)
    elif args.cmd == "sign": sign_proposal(args)
    elif args.cmd == "status": status(args)

if __name__ == "__main__":
    main()
