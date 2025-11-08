#!/usr/bin/env python3
"""Import all JSON blocks from filesystem into SQLite database."""

import json
import sqlite3
import os
from pathlib import Path
import time

# Paths
BLOCKS_DIR = Path("/home/kiana/ki_ana/memory/long_term/blocks")
DB_PATH = Path("/home/kiana/ki_ana/memory/knowledge.db")

def import_blocks():
    """Import all JSON blocks into SQLite database."""
    
    # Connect to database
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Create table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS knowledge_blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER,
        source TEXT,
        type TEXT,
        tags TEXT,
        content TEXT,
        hash TEXT,
        created_at INTEGER,
        updated_at INTEGER,
        url TEXT,
        meta TEXT
    )
    """)
    
    # Clear existing data
    cursor.execute("DELETE FROM knowledge_blocks")
    conn.commit()
    
    print(f"📂 Scanning {BLOCKS_DIR}...")
    
    # Find all JSON files
    json_files = list(BLOCKS_DIR.glob("*.json"))
    total = len(json_files)
    print(f"📊 Found {total} block files")
    
    imported = 0
    errors = 0
    
    for idx, json_file in enumerate(json_files, 1):
        try:
            # Read JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract fields (handle different formats)
            ts = data.get('timestamp') or data.get('ts') or int(time.time())
            source = data.get('source') or data.get('url') or ''
            block_type = data.get('type') or 'knowledge'
            tags = ','.join(data.get('tags', [])) if isinstance(data.get('tags'), list) else str(data.get('tags', ''))
            content = data.get('content') or data.get('text') or ''
            block_hash = data.get('hash') or ''
            created = data.get('created_at') or ts
            updated = data.get('updated_at') or ts
            url = data.get('url') or ''
            meta = json.dumps(data.get('meta', {})) if data.get('meta') else ''
            
            # Insert into database
            cursor.execute("""
                INSERT INTO knowledge_blocks 
                (ts, source, type, tags, content, hash, created_at, updated_at, url, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ts, source, block_type, tags, content, block_hash, created, updated, url, meta))
            
            imported += 1
            
            # Progress indicator
            if idx % 100 == 0:
                print(f"⏳ Progress: {idx}/{total} ({idx*100//total}%)")
                conn.commit()
        
        except Exception as e:
            errors += 1
            if errors <= 10:  # Only print first 10 errors
                print(f"⚠️  Error in {json_file.name}: {e}")
    
    # Final commit
    conn.commit()
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM knowledge_blocks")
    count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n✅ Import complete!")
    print(f"   Imported: {imported}")
    print(f"   Errors: {errors}")
    print(f"   Total in DB: {count}")
    
    return count

if __name__ == "__main__":
    start = time.time()
    count = import_blocks()
    elapsed = time.time() - start
    print(f"\n⏱️  Time: {elapsed:.2f}s")
    print(f"📊 Average: {count/elapsed:.0f} blocks/sec")
