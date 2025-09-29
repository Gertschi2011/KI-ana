#!/usr/bin/env python3
from __future__ import annotations

"""
Emergency activation CLI for KI_ana (Not‑Aus).

Safeguards:
- Verifies integrity of system/emergency_override.json against system/emergency_override.hash
- Optionally verifies access_control and chain_validator pairs
- Requires correct trigger phrase (e.g., "KIANA:CODE-RED")
- Requires passphrase whose SHA256 matches creator_passphrase_hash in emergency_override.json
- Restricts invoker to the name "Gerald" by default
- Writes KI_ROOT/emergency_stop sentinel and an audit log entry

Usage:
  python3 system/emergency_activate.py --trigger "KIANA:CODE-RED"

Flags:
  --user NAME           Override detected username (default: current user)
  --allow-user ANY      Allow any user name (disables Gerald check)
  --dry-run             Run checks only, do not activate
  --no-extra-checks     Skip access_control/chain_validator pair checks

Env:
  KI_ROOT               Base path (default: ~/ki_ana)
"""

import argparse
import getpass
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Tuple
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
        return hashlib.sha256(raw).hexdigest()
    except Exception:
        return ""


def _verify_pair(base: Path, name: str) -> Tuple[bool, str, str]:
    """Validate <name>.json against <name>.hash in base.
    Returns (ok, calc, stored)."""
    j = base / f"{name}.json"
    h = base / f"{name}.hash"
    if not j.exists() or not h.exists():
        return False, "", ""
    obj = _read_json(j)
    calc = _sha256_canonical(obj)
    stored = (h.read_text(encoding="utf-8").strip() if h.exists() else "")
    return (bool(calc and stored and calc == stored), calc, stored)


def _prompt_passphrase() -> str:
    return getpass.getpass("Passphrase: ")


def _audit_write(root: Path, payload: Dict) -> None:
    try:
        logdir = root / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        (logdir / "audit_emergency.jsonl").open("a", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Activate KI_ana emergency stop (Not‑Aus)")
    ap.add_argument("--trigger", required=True, help="Trigger phrase – must match emergency_override.json")
    ap.add_argument("--user", help="Invoker name override (default: OS user)")
    ap.add_argument("--allow-user", action="store_true", help="Allow any user (disable 'Gerald' name check)")
    ap.add_argument("--dry-run", action="store_true", help="Only verify conditions; do not activate")
    ap.add_argument("--no-extra-checks", action="store_true", help="Skip access_control/chain_validator verification")
    args = ap.parse_args(argv)

    root = _ki_root()
    sysdir = root / "system"

    # 1) Verify emergency_override pair
    ok, calc, stored = _verify_pair(sysdir, "emergency_override")
    if not ok:
        print("❌ emergency_override hash mismatch or files missing", file=sys.stderr)
        return 2

    ov = _read_json(sysdir / "emergency_override.json")
    trigger = str(ov.get("trigger_phrase") or "").strip()
    required_action = str(ov.get("action") or "").strip().lower()
    pw_hash = str(ov.get("creator_passphrase_hash") or "").strip()
    irreversible = bool(ov.get("irreversible", False))

    if not trigger or not pw_hash:
        print("❌ emergency_override missing trigger or passphrase hash", file=sys.stderr)
        return 2

    # 2) Optional extra pairs: access_control / chain_validator
    if not args.no_extra_checks:
        for name in ("access_control", "chain_validator"):
            ok2, _, _ = _verify_pair(sysdir, name)
            if not ok2:
                print(f"❌ {name} integrity check failed", file=sys.stderr)
                return 2

    # 3) User check – must be Gerald unless explicitly allowed
    # Robust OS user (ignore env override)
    try:
        os_user = (args.user or pwd.getpwuid(os.geteuid()).pw_name or "").strip()
    except Exception:
        os_user = (args.user or getpass.getuser() or "").strip()
    if not args.allow_user and os_user.lower() != "gerald":
        print(f"❌ Only Gerald may run this tool (detected: '{os_user}')", file=sys.stderr)
        return 3

    # 4) Trigger phrase must match exactly
    if args.trigger.strip() != trigger:
        print("❌ Trigger phrase mismatch", file=sys.stderr)
        return 4

    # 5) TTY requirement to avoid non-interactive remote triggers
    try:
        if not sys.stdin.isatty():
            print("❌ TTY required (run interactively)", file=sys.stderr)
            return 6
    except Exception:
        pass

    # 6) Optional creator key check (matches registry)
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
        # Soft‑fail (key not present) – still require passphrase
        pass

    # 7) Passphrase check (sha256)
    pw = _prompt_passphrase()
    got = hashlib.sha256(pw.encode("utf-8")).hexdigest()
    if got != pw_hash:
        print("❌ Passphrase invalid", file=sys.stderr)
        _audit_write(root, {"ts": int(time.time()), "event": "emergency_auth_failed", "user": os_user})
        return 5

    # 8) Final confirmation if irreversible
    if irreversible and not args.dry_run:
        ans = input("Dies ist irreversibel. Wirklich aktivieren? (YES/NO): ").strip().lower()
        if ans not in {"yes", "y"}:
            print("Abbruch.")
            return 1

    # 9) Activate: write sentinel file
    stop_file = root / "emergency_stop"
    payload = {
        "ts": int(time.time()),
        "by": os_user,
        "action": required_action or "shutdown_all_functions",
        "note": "Activated via emergency_activate.py",
        "override_hash": calc,
    }

    if args.dry_run:
        print("✅ Dry‑run OK – would write:", stop_file)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    stop_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _audit_write(root, {"ts": int(time.time()), "event": "emergency_activated", **payload})
    print(f"🛑 Emergency stop ACTIVATED at {stop_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
