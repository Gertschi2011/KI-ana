#!/usr/bin/env python3
"""
Addressbook Indexer CLI Tool
Builds topic tree index from memory blocks
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from netapi.modules.addressbook.indexer import build_addressbook_index


def main():
    """Main CLI entry point"""
    print("🗂️  KI_ana Addressbook Indexer")
    print("=" * 60)
    print()
    
    # Check for custom blocks directory
    blocks_dir = None
    if len(sys.argv) > 1:
        blocks_dir = sys.argv[1]
        print(f"📂 Custom blocks directory: {blocks_dir}")
    
    # Build index
    try:
        result = build_addressbook_index(blocks_dir)
        
        print()
        print("✅ Success!")
        print(f"   📦 Indexed blocks: {result['stats']['indexed_blocks']}")
        print(f"   📁 Total topics: {result['stats']['topics']}")
        print(f"   ⏱️  Duration: {result['stats']['duration_ms']}ms")
        print()
        print("💡 Next steps:")
        print("   • View in browser: https://ki-ana.at/static/addressbook.html")
        print("   • API endpoint: https://ki-ana.at/api/addressbook/tree")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
