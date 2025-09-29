#!/usr/bin/env python3
from __future__ import annotations

"""
Emergency deactivation CLI for KI_ana.

Safeguards:
- Verifies emergency_override integrity (json/hash)
- Requires Gerald as invoker (unless --allow-user)
- Requires correct creator passphrase (SHA256 match)
- Removes KI_ROOT/emergency_stop and writes an audit entry

Usage:
  python3 system/emergency_deactivate.py --confirm YES

Flags:
  --user NAME        Override OS user
  --allow-user       Allow any user name (keep passphrase requirement)
  --confirm YES      Safety confirmation token (required unless --force)
  --force            Skip confirmation token (still asks passphrase)
"""

import argparse
import getpass
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict
import pwd


def _ki_root() -> Path:
    return Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))).resolve()


def _read_json(p: Path) -> Dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _sha256_canonical(obj: Dict) -> str:
    try:
        raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        import hashlib as _h
        return _h.sha256(raw).hexdigest()
    except Exception:
        return ""


def _verify_pair(base: Path, name: str) -> bool:
    j = base / f"{name}.json"; h = base / f"{name}.hash"
    if not j.exists() or not h.exists():
        return False
    calc = _sha256_canonical(_read_json(j))
    return bool(calc and calc == (h.read_text(encoding="utf-8").strip()))


def _audit(root: Path, payload: Dict) -> None:
    try:
        logdir = root / "logs"; logdir.mkdir(parents=True, exist_ok=True)
        (logdir / "audit_emergency.jsonl").open("a", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Deactivate KI_ana emergency stop")
    ap.add_argument("--user", help="Invoker name override")
    ap.add_argument("--allow-user", action="store_true")
    ap.add_argument("--confirm", default="", help="Type YES to confirm")
    ap.add_argument("--force", action="store_true", help="Skip --confirm check (still requires passphrase)")
    args = ap.parse_args(argv)

    root = _ki_root()
    sysdir = root / "system"
    stopf = root / "emergency_stop"

    if not stopf.exists():
        print("ℹ️  Not active – nothing to do.")
        return 0

    if not _verify_pair(sysdir, "emergency_override"):
        print("❌ emergency_override integrity failed", file=sys.stderr)
        return 2

    try:
        os_user = (args.user or pwd.getpwuid(os.geteuid()).pw_name or "").strip()
    except Exception:
        os_user = (args.user or getpass.getuser() or "").strip()
    if not args.allow_user and os_user.lower() != "gerald":
        print(f"❌ Only Gerald may run this tool (detected: '{os_user}')", file=sys.stderr)
        return 3

    if not args.force and args.confirm.strip().upper() != "YES":
        print("❌ Please confirm with --confirm YES (or use --force)", file=sys.stderr)
        return 4

    # TTY required
    try:
        if not sys.stdin.isatty():
            print("❌ TTY required (run interactively)", file=sys.stderr)
            return 6
    except Exception:
        pass

    # Optional creator key check (registry match)
    try:
        from nacl import signing, encoding  # type: ignore
        keys_dir = sysdir / "keys"
        sk_path = keys_dir / "owner_private.key"
        reg_path = keys_dir / "identity_registry.json"
        if sk_path.exists() and reg_path.exists():
            sk = signing.SigningKey(sk_path.read_bytes())
            vk = sk.verify_key
            b64 = encoding.Base64Encoder.encode(vk.encode()).decode()
            reg = json.loads(reg_path.read_text(encoding="utf-8"))
            want = str(reg.get("owner_pubkey") or "").strip()
            if not want or b64 != want:
                print("❌ Owner key mismatch (registry)", file=sys.stderr)
                return 7
    except Exception:
        pass

    # Passphrase verification
    ov = _read_json(sysdir / "emergency_override.json")
    want_hash = str(ov.get("creator_passphrase_hash") or "").strip()
    if not want_hash:
        print("❌ Passphrase hash missing in override", file=sys.stderr)
        return 2
    pw = getpass.getpass("Passphrase: ")
    if hashlib.sha256(pw.encode("utf-8")).hexdigest() != want_hash:
        print("❌ Passphrase invalid", file=sys.stderr)
        _audit(root, {"ts": int(time.time()), "event": "emergency_deauth_failed", "user": os_user})
        return 5

    # Remove sentinel
    stopf.unlink(missing_ok=True)
    _audit(root, {"ts": int(time.time()), "event": "emergency_deactivated", "by": os_user})
    print("✅ Emergency stop DEACTIVATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
