#!/usr/bin/env python3
"""
Rehash und verifiziere alle Knowledge Blöcke.
Berechnet SHA256 Hashes neu und updated die JSON-Dateien.
"""

import json
import hashlib
from pathlib import Path
import time

# Paths
KI_ROOT = Path("/home/kiana/ki_ana")
BLOCKS_DIR = KI_ROOT / "memory" / "long_term" / "blocks"
CHAIN_DIR = KI_ROOT / "system" / "chain"

def hash_content(data: dict) -> str:
    """Calculate SHA256 hash of block content (excluding signature and hash)."""
    # Remove signature and hash fields for clean calculation
    clean_data = {k: v for k, v in data.items() if k not in ['signature', 'hash', 'sig']}
    
    # Sort keys for consistent hashing
    content_str = json.dumps(clean_data, sort_keys=True, ensure_ascii=False)
    
    # Calculate SHA256
    return hashlib.sha256(content_str.encode('utf-8')).hexdigest()

def process_block(file_path: Path) -> tuple[str, str, str]:
    """
    Process a single block file.
    Returns: (status, old_hash, new_hash)
    """
    try:
        # Read block
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Calculate new hash
        new_hash = hash_content(data)
        old_hash = data.get('hash', '')
        
        # Update hash if different
        if old_hash != new_hash:
            data['hash'] = new_hash
            
            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return ('updated', old_hash, new_hash)
        else:
            return ('ok', old_hash, new_hash)
            
    except json.JSONDecodeError as e:
        return (f'json_error: {e}', '', '')
    except Exception as e:
        return (f'error: {e}', '', '')

def main():
    """Main rehashing process."""
    print("=" * 60)
    print("🔄 KI_ana Block Rehashing Tool")
    print("=" * 60)
    print(f"\n📂 Blocks Directory: {BLOCKS_DIR}")
    print(f"📂 Chain Directory: {CHAIN_DIR}")
    print()
    
    start_time = time.time()
    
    # Statistics
    stats = {
        'total': 0,
        'updated': 0,
        'ok': 0,
        'errors': 0,
        'json_errors': 0
    }
    
    # Process memory blocks
    if BLOCKS_DIR.exists():
        print(f"📦 Processing memory blocks from: {BLOCKS_DIR}")
        block_files = sorted(BLOCKS_DIR.glob("*.json"))
        total_files = len(block_files)
        print(f"   Found {total_files} block files\n")
        
        for idx, block_file in enumerate(block_files, 1):
            stats['total'] += 1
            status, old_hash, new_hash = process_block(block_file)
            
            if status == 'updated':
                stats['updated'] += 1
            elif status == 'ok':
                stats['ok'] += 1
            elif 'json_error' in status:
                stats['json_errors'] += 1
                if stats['json_errors'] <= 5:  # Show first 5 errors
                    print(f"   ⚠️  JSON Error in {block_file.name}: {status}")
            else:
                stats['errors'] += 1
                if stats['errors'] <= 5:
                    print(f"   ❌ Error in {block_file.name}: {status}")
            
            # Progress indicator every 500 blocks
            if idx % 500 == 0:
                elapsed = time.time() - start_time
                rate = idx / elapsed if elapsed > 0 else 0
                print(f"   ⏳ Progress: {idx}/{total_files} ({idx*100//total_files}%) - {rate:.0f} blocks/sec")
    else:
        print(f"⚠️  Blocks directory not found: {BLOCKS_DIR}")
    
    # Process chain blocks
    if CHAIN_DIR.exists():
        print(f"\n⛓️  Processing chain blocks from: {CHAIN_DIR}")
        chain_files = sorted(CHAIN_DIR.glob("*.json"))
        print(f"   Found {len(chain_files)} chain files\n")
        
        for block_file in chain_files:
            stats['total'] += 1
            status, old_hash, new_hash = process_block(block_file)
            
            if status == 'updated':
                stats['updated'] += 1
            elif status == 'ok':
                stats['ok'] += 1
            elif 'json_error' in status:
                stats['json_errors'] += 1
            else:
                stats['errors'] += 1
    else:
        print(f"⚠️  Chain directory not found: {CHAIN_DIR}")
    
    # Final statistics
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("✅ REHASHING COMPLETE!")
    print("=" * 60)
    print(f"\n📊 Statistics:")
    print(f"   Total Blocks:     {stats['total']}")
    print(f"   ✅ Updated:       {stats['updated']}")
    print(f"   ✓  Already OK:    {stats['ok']}")
    print(f"   ⚠️  JSON Errors:   {stats['json_errors']}")
    print(f"   ❌ Other Errors:  {stats['errors']}")
    print(f"\n⏱️  Time: {elapsed:.2f} seconds")
    print(f"📈 Rate: {stats['total']/elapsed:.0f} blocks/second")
    print()
    
    # Summary
    if stats['updated'] > 0:
        print(f"🔄 {stats['updated']} blocks were rehashed with new hash values.")
    if stats['errors'] + stats['json_errors'] > 0:
        print(f"⚠️  {stats['errors'] + stats['json_errors']} blocks had errors (check logs above).")
    if stats['ok'] > 0:
        print(f"✓  {stats['ok']} blocks already had correct hashes.")
    
    print("\n🎉 All blocks have been processed!")
    return stats

if __name__ == "__main__":
    stats = main()
