#!/usr/bin/env python3
"""
Signiere alle Knowledge Blöcke mit Ed25519.
"""

import json
import sys
from pathlib import Path
import time

# Add system path
sys.path.insert(0, str(Path(__file__).parent / "system"))

try:
    from block_signer import sign_block, ensure_keys
except ImportError:
    print("❌ Konnte block_signer nicht importieren!")
    sys.exit(1)

# Paths
KI_ROOT = Path("/home/kiana/ki_ana")
BLOCKS_DIR = KI_ROOT / "memory" / "long_term" / "blocks"
CHAIN_DIR = KI_ROOT / "system" / "chain"

def process_block(file_path: Path) -> str:
    """Sign a single block file."""
    try:
        # Read block
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if already signed
        if data.get('signature'):
            return 'already_signed'
        
        # Sign block
        signature, pubkey, signed_at = sign_block(data)
        
        # Update block with signature
        data['signature'] = signature
        data['pubkey'] = pubkey
        data['signed_at'] = signed_at
        
        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return 'signed'
        
    except json.JSONDecodeError as e:
        return f'json_error: {e}'
    except Exception as e:
        return f'error: {e}'

def main():
    """Main signing process."""
    print("=" * 60)
    print("🔐 KI_ana Block Signing Tool")
    print("=" * 60)
    
    # Ensure keys exist
    try:
        pub_b64, _ = ensure_keys()
        print(f"\n🔑 Public Key: {pub_b64[:16]}...{pub_b64[-16:]}")
    except Exception as e:
        print(f"❌ Fehler beim Laden der Keys: {e}")
        return
    
    print(f"\n📂 Blocks Directory: {BLOCKS_DIR}")
    print(f"📂 Chain Directory: {CHAIN_DIR}")
    print()
    
    start_time = time.time()
    
    # Statistics
    stats = {
        'total': 0,
        'signed': 0,
        'already_signed': 0,
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
            result = process_block(block_file)
            
            if result == 'signed':
                stats['signed'] += 1
            elif result == 'already_signed':
                stats['already_signed'] += 1
            elif 'json_error' in result:
                stats['json_errors'] += 1
            else:
                stats['errors'] += 1
                if stats['errors'] <= 5:
                    print(f"   ❌ Error in {block_file.name}: {result}")
            
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
            result = process_block(block_file)
            
            if result == 'signed':
                stats['signed'] += 1
            elif result == 'already_signed':
                stats['already_signed'] += 1
            elif 'json_error' in result:
                stats['json_errors'] += 1
            else:
                stats['errors'] += 1
    else:
        print(f"⚠️  Chain directory not found: {CHAIN_DIR}")
    
    # Final statistics
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("✅ SIGNING COMPLETE!")
    print("=" * 60)
    print(f"\n📊 Statistics:")
    print(f"   Total Blocks:      {stats['total']}")
    print(f"   🔐 Neu signiert:   {stats['signed']}")
    print(f"   ✓  Bereits sign.:  {stats['already_signed']}")
    print(f"   ⚠️  JSON Errors:    {stats['json_errors']}")
    print(f"   ❌ Other Errors:   {stats['errors']}")
    print(f"\n⏱️  Time: {elapsed:.2f} seconds")
    if elapsed > 0:
        print(f"📈 Rate: {stats['total']/elapsed:.0f} blocks/second")
    print()
    
    # Summary
    if stats['signed'] > 0:
        print(f"🔐 {stats['signed']} blocks were signed with new signatures.")
    if stats['already_signed'] > 0:
        print(f"✓  {stats['already_signed']} blocks were already signed.")
    if stats['errors'] + stats['json_errors'] > 0:
        print(f"⚠️  {stats['errors'] + stats['json_errors']} blocks had errors.")
    
    print("\n🎉 All blocks have been processed!")
    return stats

if __name__ == "__main__":
    stats = main()
