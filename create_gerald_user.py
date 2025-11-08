#!/usr/bin/env python3
"""
Create user 'gerald' as Creator/Papa in the database
"""
from backend.core.db import Session, Base, init_db
from sqlalchemy import text
import argon2

# Initialize DB
init_db()

# Hash password
ph = argon2.PasswordHasher()
password_hash = ph.hash("Jawohund2011!")

session = Session()

try:
    # Create users table if not exists
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(50) DEFAULT 'user',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            papa_mode BOOLEAN DEFAULT FALSE
        )
    """))
    session.commit()
    print("✅ Users table created/verified")
    
    # Check if gerald exists
    result = session.execute(text("SELECT id FROM users WHERE username = 'gerald'"))
    existing = result.fetchone()
    
    if existing:
        # Update existing user
        session.execute(text("""
            UPDATE users 
            SET password_hash = :hash, 
                role = 'admin', 
                papa_mode = TRUE,
                is_active = TRUE
            WHERE username = 'gerald'
        """), {"hash": password_hash})
        print("✅ User 'gerald' updated")
    else:
        # Create new user
        session.execute(text("""
            INSERT INTO users (username, email, password_hash, role, papa_mode, is_active)
            VALUES ('gerald', 'gerald@ki-ana.at', :hash, 'admin', TRUE, TRUE)
        """), {"hash": password_hash})
        print("✅ User 'gerald' created")
    
    session.commit()
    
    # Verify
    result = session.execute(text("SELECT username, email, role, papa_mode FROM users WHERE username = 'gerald'"))
    user = result.fetchone()
    if user:
        print(f"\n✅ User verified:")
        print(f"   Username: {user[0]}")
        print(f"   Email: {user[1]}")
        print(f"   Role: {user[2]}")
        print(f"   Papa Mode: {user[3]}")
    
except Exception as e:
    session.rollback()
    print(f"❌ Error: {e}")
    raise
finally:
    session.close()

print("\n✅ Setup complete!")
print("   Login: gerald")
print("   Password: Jawohund2011!")
