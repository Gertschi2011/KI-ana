# netapi/modules/auth/crypto.py
from werkzeug.security import check_password_hash, generate_password_hash

def hash_pw(pw: str) -> str:
    return generate_password_hash(pw)

def check_pw(pw: str, hashed: str) -> bool:
    try:
        return check_password_hash(hashed, pw)
    except Exception:
        return False