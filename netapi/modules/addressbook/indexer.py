"""
Addressbook Indexer
Scans memory blocks and builds a hierarchical topic tree
"""
import json
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict


class AddressbookIndexer:
    """Builds and maintains a topic tree from memory blocks"""
    
    def __init__(self, blocks_dir: str = "/home/kiana/ki_ana/memory/long_term/blocks"):
        self.blocks_dir = Path(blocks_dir)
        self.index_file = Path("/home/kiana/ki_ana/data/addressbook.index.json")
        self.tree = {}
        self.stats = {
            "total_blocks": 0,
            "indexed_blocks": 0,
            "topics": 0,
            "last_updated": 0,
            "duration_ms": 0
        }
    
    def build_index(self) -> Dict[str, Any]:
        """Build complete index from scratch"""
        start_time = time.time()
        print(f"🔍 Scanning blocks in: {self.blocks_dir}")
        
        # Reset
        self.tree = {}
        self.stats["total_blocks"] = 0
        self.stats["indexed_blocks"] = 0
        
        # Scan all JSON files
        block_files = list(self.blocks_dir.glob("**/*.json"))
        block_files.extend(self.blocks_dir.glob("**/*.jsonl"))
        
        self.stats["total_blocks"] = len(block_files)
        print(f"📦 Found {len(block_files)} block files")
        
        # Process each block
        for block_file in block_files:
            try:
                self._process_block_file(block_file)
            except Exception as e:
                print(f"⚠️  Error processing {block_file.name}: {e}")
        
        # Build hierarchical tree
        tree_data = self._build_tree()
        
        # Finalize stats
        self.stats["topics"] = self._count_topics(tree_data)
        self.stats["last_updated"] = int(time.time())
        self.stats["duration_ms"] = int((time.time() - start_time) * 1000)
        
        # Save index
        index_data = {
            "tree": tree_data,
            "stats": self.stats,
            "version": "1.0"
        }
        
        self._save_index(index_data)
        
        print(f"✅ Index built: {self.stats['indexed_blocks']} blocks, {self.stats['topics']} topics")
        print(f"⏱️  Duration: {self.stats['duration_ms']}ms")
        
        return index_data
    
    def _process_block_file(self, file_path: Path):
        """Process a single block file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Handle both JSON and JSONL
                content = f.read().strip()
                
                if file_path.suffix == '.jsonl':
                    # JSONL: multiple lines
                    for line in content.split('\n'):
                        if line.strip():
                            block = json.loads(line)
                            self._index_block(block, file_path)
                else:
                    # Regular JSON
                    block = json.loads(content)
                    self._index_block(block, file_path)
                    
        except json.JSONDecodeError as e:
            print(f"⚠️  Invalid JSON in {file_path.name}: {e}")
        except Exception as e:
            print(f"⚠️  Error reading {file_path.name}: {e}")
    
    def _index_block(self, block: Dict[str, Any], file_path: Path):
        """Add a single block to the index"""
        # Extract topic path
        topics_path = self._extract_topic_path(block)
        
        if not topics_path:
            # No topics - add to "Uncategorized"
            topics_path = ["Uncategorized"]
        
        # Get block metadata
        block_id = block.get('id', file_path.stem)
        title = block.get('title', 'Untitled')
        timestamp = block.get('timestamp', block.get('created_at', 0))
        trust = block.get('trust', block.get('rating', 5))
        
        # Build path key
        path_key = '/'.join(topics_path)
        
        # Add to tree
        if path_key not in self.tree:
            self.tree[path_key] = {
                "path": topics_path,
                "blocks": [],
                "count": 0
            }
        
        self.tree[path_key]["blocks"].append({
            "id": block_id,
            "title": title,
            "timestamp": timestamp,
            "trust": trust,
            "file": str(file_path.relative_to(self.blocks_dir))
        })
        
        self.tree[path_key]["count"] += 1
        self.stats["indexed_blocks"] += 1
    
    def _extract_topic_path(self, block: Dict[str, Any]) -> List[str]:
        """Extract topic path from block"""
        # Try different field names
        for field in ['topics_path', 'topic_path', 'topics', 'topic', 'tags']:
            if field in block:
                value = block[field]
                
                # If it's already a list
                if isinstance(value, list):
                    return [str(t).strip() for t in value if t]
                
                # If it's a string with slashes
                if isinstance(value, str) and '/' in value:
                    return [t.strip() for t in value.split('/') if t.strip()]
                
                # If it's a single string
                if isinstance(value, str) and value.strip():
                    return [value.strip()]
        
        # Try extracting from title or topic field
        title = block.get('title', '')
        topic = block.get('topic', '')
        
        # Simple heuristic: if title starts with a category, use it
        if '/' in title:
            parts = title.split('/')
            if len(parts) >= 2:
                return [p.strip() for p in parts[:-1]]
        
        if topic:
            return [str(topic).strip()]
        
        return []
    
    def _build_tree(self) -> Dict[str, Any]:
        """Build hierarchical tree structure"""
        root = {
            "name": "root",
            "path": [],
            "count": 0,
            "children": {},
            "blocks": []
        }
        
        # Process each path
        for path_key, data in self.tree.items():
            path = data["path"]
            blocks = data["blocks"]
            
            # Navigate/create tree structure
            current = root
            for i, topic in enumerate(path):
                if topic not in current["children"]:
                    current["children"][topic] = {
                        "name": topic,
                        "path": path[:i+1],
                        "count": 0,
                        "children": {},
                        "blocks": []
                    }
                
                current = current["children"][topic]
                current["count"] += len(blocks)
            
            # Add blocks to leaf node
            current["blocks"] = blocks
        
        return self._serialize_tree(root)
    
    def _serialize_tree(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Convert tree to serializable format"""
        result = {
            "name": node["name"],
            "path": node["path"],
            "count": node["count"],
            "blocks_count": len(node.get("blocks", [])),
            "children": []
        }
        
        # Add children (sorted by name)
        if node["children"]:
            for name in sorted(node["children"].keys()):
                result["children"].append(
                    self._serialize_tree(node["children"][name])
                )
        
        return result
    
    def _count_topics(self, tree: Dict[str, Any]) -> int:
        """Count total number of topics in tree"""
        count = 1  # Count self
        for child in tree.get("children", []):
            count += self._count_topics(child)
        return count
    
    def _save_index(self, data: Dict[str, Any]):
        """Save index to file"""
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Index saved to: {self.index_file}")
    
    def load_index(self) -> Optional[Dict[str, Any]]:
        """Load existing index"""
        if not self.index_file.exists():
            return None
        
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading index: {e}")
            return None


# Standalone function for external use
def build_addressbook_index(blocks_dir: str = None) -> Dict[str, Any]:
    """Build addressbook index (standalone function)"""
    if blocks_dir is None:
        blocks_dir = "/home/kiana/ki_ana/memory/long_term/blocks"
    
    indexer = AddressbookIndexer(blocks_dir)
    return indexer.build_index()


if __name__ == "__main__":
    # CLI usage
    print("🗂️  KI_ana Addressbook Indexer")
    print("=" * 50)
    build_addressbook_index()
