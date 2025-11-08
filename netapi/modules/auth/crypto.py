# netapi/modules/auth/crypto.py
from werkzeug.security import check_password_hash, generate_password_hash

def hash_pw(pw: str) -> str:
    """Generate password hash using scrypt (werkzeug default)"""
    return generate_password_hash(pw)

def check_pw(pw: str, hashed: str) -> bool:
    """
    Check password against hash.
    Supports BOTH scrypt (new) and argon2 (legacy from Flask backend).
    """
    # Try scrypt first (current format)
    try:
        if check_password_hash(hashed, pw):
            return True
    except Exception:
        pass
    
    # Try argon2 (legacy format from old Flask backend)
    if hashed.startswith("$argon2"):
        try:
            from argon2 import PasswordHasher
            ph = PasswordHasher()
            ph.verify(hashed, pw)
            return True
        except Exception:
            # argon2 not installed or verification failed
            pass
    
    return False