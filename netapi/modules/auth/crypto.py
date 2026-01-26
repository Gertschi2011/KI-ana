"""Password hashing helpers.

Goals:
- Use a modern password hash for NEW registrations (bcrypt).
- Stay backward-compatible with existing hashes:
  - Werkzeug `generate_password_hash` (scrypt/pbkdf2 formats like `scrypt:...`)
  - Legacy argon2 hashes from the old backend.

Implementation note:
- We intentionally avoid passlib's bcrypt backend auto-detection here because
  some bcrypt backends raise on >72-byte inputs during passlib's self-tests.
- We pre-hash the password with SHA-256 before bcrypt so we never hit bcrypt's
  72-byte limit while keeping verification stable.
"""

from __future__ import annotations

import hashlib

from werkzeug.security import check_password_hash


def _pw_bytes(pw: str) -> bytes:
    # bcrypt has a 72-byte input limit; pre-hash for safety.
    return hashlib.sha256((pw or "").encode("utf-8")).digest()


def hash_pw(pw: str) -> str:
    """Hash password for storage (bcrypt, SHA-256 prehash)."""
    try:
        import bcrypt  # type: ignore

        return bcrypt.hashpw(_pw_bytes(pw), bcrypt.gensalt()).decode("utf-8")
    except Exception:
        # Fallback: Werkzeug scrypt (still strong, but we prefer bcrypt when available)
        from werkzeug.security import generate_password_hash

        return generate_password_hash(pw)


def check_pw(pw: str, hashed: str) -> bool:
    """Verify password against stored hash."""
    h = (hashed or "").strip()
    if not pw or not h:
        return False

    # Werkzeug formats (current/legacy in this project)
    if h.startswith("scrypt:") or h.startswith("pbkdf2:"):
        try:
            return bool(check_password_hash(h, pw))
        except Exception:
            return False

    # Legacy argon2 from older backend
    if h.startswith("$argon2"):
        try:
            from argon2 import PasswordHasher

            ph = PasswordHasher()
            ph.verify(h, pw)
            return True
        except Exception:
            return False

    # bcrypt hashes ($2a$, $2b$, $2y$)
    if h.startswith("$2"):
        try:
            import bcrypt  # type: ignore

            return bool(bcrypt.checkpw(_pw_bytes(pw), h.encode("utf-8")))
        except Exception:
            return False

    return False