#!/usr/bin/env python3
import argparse, json, tarfile, os, base64, shutil
from pathlib import Path

BASE      = Path.home() / "ki_ana"
RUNTIME   = BASE / "system" / "submind_runtime"
KEYS      = BASE / "system" / "keys"
REG       = KEYS / "identity_registry.json"
OUTDIR    = BASE / "subminds" / "dist"

def load_registry():
    return json.loads(REG.read_text(encoding="utf-8"))

def get_owner_pubkey():
    reg = load_registry()
    return reg.get("owner_pubkey","")

def get_submind_pubkey(submind_id: str) -> str:
    reg = load_registry()
    for s in reg.get("subminds", []):
        if s.get("id") == submind_id:
            return s.get("pubkey","")
    raise SystemExit(f"Submind {submind_id} nicht in Registry")

def make_config(submind_id: str, license_key: str, parent_endpoint: str) -> bytes:
    tpl = (RUNTIME / "config.template.json").read_text(encoding="utf-8")
    tpl = tpl.replace("{{ID}}", submind_id)
    tpl = tpl.replace("{{LICENSE}}", license_key)
    tpl = tpl.replace("{{PARENT_ENDPOINT}}", parent_endpoint)
    tpl = tpl.replace("{{PARENT_PUBKEY}}", get_owner_pubkey())
    return tpl.encode("utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="Submind-ID (z.B. emo-001)")
    ap.add_argument("--license", required=True, help="Lizenz- oder Aktivierungscode")
    ap.add_argument("--parent-endpoint", default="https://example.invalid/api", help="Endpoint der Mutter-KI")
    args = ap.parse_args()

    # Zielordner vorbereiten
    OUTDIR.mkdir(parents=True, exist_ok=True)
    work = OUTDIR / f"{args.id}_build"
    if work.exists(): shutil.rmtree(work)
    shutil.copytree(RUNTIME, work)

    # config.json aus Template erzeugen
    (work / "config.json").write_bytes(make_config(args.id, args.license, args.parent_endpoint))

    # README beilegen
    (work / "README.txt").write_text(
        "Submind Paket\n"
        f"ID: {args.id}\n"
        "Installation: ./install_submind.sh [Zielpfad]\n"
        "Start: <Zielpfad>/.venv/bin/python runtime_listener.py\n",
        encoding="utf-8"
    )

    # Archiv erstellen
    tarpath = OUTDIR / f"submind_{args.id}.tar.gz"
    with tarfile.open(tarpath, "w:gz") as tar:
        tar.add(work, arcname=f"submind_{args.id}")
    shutil.rmtree(work)

    print("✅ Paket erstellt:", tarpath)

if __name__ == "__main__":
    main()
