#!/usr/bin/env python3
"""Reset a user's password.

Designed for ops usage (e.g. prod containers):
- Reads the new password via secure prompt (TTY) by default.
- Alternatively accepts it via env var NEW_PASSWORD.

Usage:
  python3 RESET_GERALD_PASSWORD.py --email gerald.stiefsohn@gmx.at
  NEW_PASSWORD='...' python3 RESET_GERALD_PASSWORD.py --email gerald.stiefsohn@gmx.at
"""

from __future__ import annotations

import argparse
import os
import sys
from getpass import getpass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset a user's password")
    parser.add_argument("--email", required=True, help="User email to reset")
    return parser.parse_args()


def _get_new_password() -> str:
    env_pw = (os.environ.get("NEW_PASSWORD") or "").strip()
    if env_pw:
        return env_pw

    pw1 = getpass("New password: ")
    pw2 = getpass("Repeat password: ")
    if pw1 != pw2:
        raise SystemExit("Passwords do not match")
    if not pw1:
        raise SystemExit("Empty password is not allowed")
    return pw1


def main() -> int:
    args = _parse_args()
    sys.path.insert(0, "/home/kiana/ki_ana")

    import os
    from netapi.modules.auth.crypto import hash_pw

    email = args.email.strip()
    print(f"🔐 Resetting password for {email}")
    print("=" * 60)

    new_password = _get_new_password()

    db_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not db_url:
        try:
            import netapi.db as d
            db_url = (getattr(d, "DB_URL", "") or "").strip()
        except Exception:
            db_url = ""
    if not db_url:
        print("❌ Error: missing DATABASE_URL")
        return 2

    new_hash = hash_pw(new_password)

    def _sqlite_path(url: str) -> str:
        url = url.split("?", 1)[0]
        if url.startswith("sqlite:////"):
            return "/" + url[len("sqlite:////") :]
        if url.startswith("sqlite:///"):
            return "/" + url[len("sqlite:///") :]
        if url.startswith("sqlite://"):
            return url[len("sqlite://") :]
        return url

    try:
        if db_url.startswith("sqlite:"):
            import sqlite3

            path = _sqlite_path(db_url)
            conn = sqlite3.connect(path)
            try:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE users SET password_hash = ? WHERE lower(email)=lower(?)",
                    (new_hash, email),
                )
                if cur.rowcount == 0:
                    print(f"❌ User with email {email} not found!")
                    return 1
                conn.commit()
                cur.execute(
                    "SELECT id, username, email FROM users WHERE lower(email)=lower(?) LIMIT 1",
                    (email,),
                )
                row = cur.fetchone()
                if row:
                    print(f"✅ Found user: {row[1]} (ID={row[0]})")
                print("✅ Password updated")
                print("   Password: (hidden)")
                return 0
            finally:
                conn.close()
        else:
            from sqlalchemy import create_engine, text

            eng = create_engine(db_url, future=True)
            with eng.begin() as conn:
                r = conn.execute(
                    text("UPDATE users SET password_hash=:h WHERE lower(email)=lower(:e)"),
                    {"h": new_hash, "e": email},
                )
                if (getattr(r, "rowcount", 0) or 0) == 0:
                    print(f"❌ User with email {email} not found!")
                    return 1
            print("✅ Password updated")
            print("   Password: (hidden)")
            return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
