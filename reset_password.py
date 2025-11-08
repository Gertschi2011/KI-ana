#!/usr/bin/env python3
"""
Script zum Zurücksetzen des Passworts für einen User.
Kann lokal oder auf dem Production-Server ausgeführt werden.
"""

import sys
import time
from netapi.db import SessionLocal
from netapi.models import User
from netapi.modules.auth.crypto import hash_pw, check_pw


def reset_password(username: str, new_password: str):
    """Setzt das Passwort für einen User zurück."""
    with SessionLocal() as db:
        # Case-insensitive username lookup
        from sqlalchemy import func
        user = db.query(User).filter(func.lower(User.username) == username.lower()).first()
        
        if not user:
            print(f"❌ User '{username}' nicht gefunden")
            return False
        
        print(f"✅ User gefunden: {user.username}")
        print(f"   ID: {user.id}")
        print(f"   Email: {user.email}")
        print(f"   Role: {user.role}")
        print(f"   Status: {getattr(user, 'status', 'active')}")
        
        # Set new password
        user.password_hash = hash_pw(new_password)
        user.updated_at = int(time.time())
        db.commit()
        
        # Verify
        db.refresh(user)
        if check_pw(new_password, user.password_hash):
            print(f"\n✅ Passwort erfolgreich zurückgesetzt!")
            print(f"   Username: {user.username}")
            print(f"   Neues Passwort: {new_password}")
            return True
        else:
            print(f"\n❌ Fehler: Passwort-Verifikation fehlgeschlagen")
            return False


def list_users():
    """Listet alle User auf."""
    with SessionLocal() as db:
        users = db.query(User).all()
        print(f"\n📋 Gefundene User ({len(users)}):\n")
        
        for u in users:
            status = getattr(u, 'status', 'active')
            print(f"  • {u.username:20} (ID: {u.id:3}, Role: {u.role:10}, Status: {status})")
            if u.email:
                print(f"    Email: {u.email}")
        print()


if __name__ == "__main__":
    print("=" * 60)
    print("KI_ana Passwort-Reset Tool")
    print("=" * 60)
    
    if len(sys.argv) == 1:
        # No arguments: list users
        list_users()
        print("Usage:")
        print("  python3 reset_password.py <username> <new_password>")
        print("\nBeispiel:")
        print("  python3 reset_password.py gerald kiana")
        sys.exit(0)
    
    if len(sys.argv) != 3:
        print("❌ Fehler: Falsche Anzahl Argumente")
        print("\nUsage:")
        print("  python3 reset_password.py <username> <new_password>")
        sys.exit(1)
    
    username = sys.argv[1]
    new_password = sys.argv[2]
    
    print(f"\n🔐 Passwort zurücksetzen für: {username}")
    print(f"   Neues Passwort: {new_password}")
    print()
    
    success = reset_password(username, new_password)
    
    if success:
        print("\n" + "=" * 60)
        print("✅ ERFOLGREICH")
        print("=" * 60)
        print(f"\nLogin-Daten:")
        print(f"  Username: {username}")
        print(f"  Passwort: {new_password}")
        print()
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ FEHLER")
        print("=" * 60)
        sys.exit(1)
