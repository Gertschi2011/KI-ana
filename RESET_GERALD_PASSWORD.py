#!/usr/bin/env python3
"""
Reset Gerald's password to a known value
Run with: python3 RESET_GERALD_PASSWORD.py
"""
import sys
sys.path.insert(0, '/home/kiana/ki_ana')

from netapi.db import SessionLocal
from netapi.models import User
from netapi.modules.auth.crypto import hash_pw

NEW_PASSWORD = "Jawohund2011!"
EMAIL = "gerald.stiefsohn@gmx.at"

print(f"🔐 Resetting password for {EMAIL}")
print("="*60)

db = SessionLocal()
try:
    user = db.query(User).filter(User.email == EMAIL).first()
    
    if not user:
        print(f"❌ User with email {EMAIL} not found!")
        sys.exit(1)
    
    print(f"✅ Found user: {user.username} (ID={user.id})")
    
    # Set new password
    new_hash = hash_pw(NEW_PASSWORD)
    user.password_hash = new_hash
    db.commit()
    
    print(f"✅ Password hash updated!")
    print(f"   New hash: {new_hash[:60]}...")
    print()
    print(f"🔐 New credentials:")
    print(f"   Username: {user.username}")
    print(f"   Email: {EMAIL}")
    print(f"   Password: {NEW_PASSWORD}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    db.rollback()
finally:
    db.close()

print("="*60)
print("✅ Done! Try logging in now.")
