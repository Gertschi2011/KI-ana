#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/kiana/ki_ana')

import psycopg2
from netapi.modules.auth.crypto import hash_pw

# NEUES Passwort OHNE Ausrufezeichen
NEW_PASSWORD = "Jawohund2011"
EMAIL = "gerald.stiefsohn@gmx.at"

print(f"Changing password to: {NEW_PASSWORD}")

conn = psycopg2.connect(
    host="localhost", port=5432, database="kiana",
    user="kiana", password="kiana_pass"
)

cur = conn.cursor()
cur.execute("SELECT id, username FROM users WHERE email = %s", (EMAIL,))
user = cur.fetchone()

if user:
    user_id, username = user
    print(f"Found user: {username}")
    
    new_hash = hash_pw(NEW_PASSWORD)
    print(f"New hash: {new_hash[:60]}...")
    
    cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
    conn.commit()
    
    print("Password changed successfully!")
    print(f"Username: {username}")
    print(f"New Password: {NEW_PASSWORD}")

cur.close()
conn.close()
