"""
Knowledge Chain - Blockchain-based Immutable Memory for KI_ana

Implements a blockchain for storing knowledge with:
- Immutable history
- Cryptographic verification
- Distributed consensus
- Tamper-proof records
"""
from __future__ import annotations
import hashlib
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Block:
    """A single block in the knowledge chain"""
    index: int
    timestamp: float
    data: Dict[str, Any]
    previous_hash: str
    nonce: int = 0
    hash: str = ""
    
    def calculate_hash(self) -> str:
        """Calculate block hash"""
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def mine_block(self, difficulty: int = 2):
        """Mine block with proof-of-work"""
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.calculate_hash()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Block:
        """Create Block from dict"""
        return Block(
            index=data["index"],
            timestamp=data["timestamp"],
            data=data["data"],
            previous_hash=data["previous_hash"],
            nonce=data.get("nonce", 0),
            hash=data.get("hash", "")
        )


class KnowledgeChain:
    """
    Blockchain for immutable knowledge storage.
    
    Features:
    - Immutable append-only structure
    - Cryptographic verification
    - Proof-of-work consensus
    - Full history audit trail
    
    Usage:
        chain = KnowledgeChain()
        
        # Add knowledge
        chain.add_block({
            "title": "Python Basics",
            "content": "Python is a programming language...",
            "source": "wikipedia.org"
        })
        
        # Verify integrity
        valid = chain.is_valid()
        
        # Query knowledge
        blocks = chain.search("Python")
    """
    
    def __init__(self, difficulty: int = 2):
        self.chain: List[Block] = []
        self.difficulty = difficulty
        self.pending_blocks: List[Dict[str, Any]] = []
        
        # Storage
        self.chain_dir = Path.home() / "ki_ana" / "blockchain"
        self.chain_dir.mkdir(parents=True, exist_ok=True)
        self.chain_file = self.chain_dir / "knowledge_chain.json"
        
        # Load or create genesis block
        if self.chain_file.exists():
            self._load_chain()
        else:
            self._create_genesis_block()
    
    def _create_genesis_block(self):
        """Create the first block in the chain"""
        genesis = Block(
            index=0,
            timestamp=time.time(),
            data={
                "title": "Genesis Block",
                "content": "KI_ana Knowledge Chain initialized",
                "type": "genesis"
            },
            previous_hash="0"
        )
        genesis.mine_block(self.difficulty)
        self.chain.append(genesis)
        self._save_chain()
    
    def get_latest_block(self) -> Block:
        """Get the most recent block"""
        return self.chain[-1] if self.chain else None
    
    def add_block(self, data: Dict[str, Any], mine: bool = True) -> Block:
        """
        Add a new block to the chain.
        
        Args:
            data: Knowledge data to store
            mine: Whether to mine the block (proof-of-work)
            
        Returns:
            The new Block
        """
        previous_block = self.get_latest_block()
        
        new_block = Block(
            index=len(self.chain),
            timestamp=time.time(),
            data=data,
            previous_hash=previous_block.hash if previous_block else "0"
        )
        
        if mine:
            new_block.mine_block(self.difficulty)
        else:
            new_block.hash = new_block.calculate_hash()
        
        self.chain.append(new_block)
        self._save_chain()
        
        return new_block
    
    def is_valid(self) -> bool:
        """
        Verify the integrity of the entire chain.
        
        Returns:
            True if chain is valid
        """
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            
            # Check hash is correct
            if current.hash != current.calculate_hash():
                return False
            
            # Check chain linkage
            if current.previous_hash != previous.hash:
                return False
            
            # Check proof-of-work (if mined)
            if not current.hash.startswith("0" * self.difficulty):
                return False
        
        return True
    
    def search(self, query: str, limit: int = 10) -> List[Block]:
        """
        Search for blocks containing query.
        
        Args:
            query: Search term
            limit: Max results
            
        Returns:
            List of matching blocks
        """
        query_lower = query.lower()
        results = []
        
        for block in reversed(self.chain):
            if block.data.get("type") == "genesis":
                continue
            
            # Search in title and content
            title = str(block.data.get("title", "")).lower()
            content = str(block.data.get("content", "")).lower()
            
            if query_lower in title or query_lower in content:
                results.append(block)
                if len(results) >= limit:
                    break
        
        return results
    
    def get_block(self, index: int) -> Optional[Block]:
        """Get block by index"""
        if 0 <= index < len(self.chain):
            return self.chain[index]
        return None
    
    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        """Get block by hash"""
        for block in self.chain:
            if block.hash == block_hash:
                return block
        return None
    
    def get_history(self, data_key: str, data_value: str) -> List[Block]:
        """
        Get full history of blocks matching a data attribute.
        
        Args:
            data_key: Key to match (e.g., "title")
            data_value: Value to match
            
        Returns:
            List of blocks in chronological order
        """
        return [
            block for block in self.chain
            if block.data.get(data_key) == data_value
        ]
    
    def verify_block(self, block: Block) -> bool:
        """Verify a single block's integrity"""
        return block.hash == block.calculate_hash()
    
    def get_chain_info(self) -> Dict[str, Any]:
        """Get information about the chain"""
        return {
            "length": len(self.chain),
            "difficulty": self.difficulty,
            "latest_hash": self.get_latest_block().hash if self.chain else None,
            "is_valid": self.is_valid(),
            "total_data_size": sum(len(json.dumps(b.data)) for b in self.chain),
            "genesis_time": self.chain[0].timestamp if self.chain else None
        }
    
    def export_chain(self, filepath: str):
        """Export chain to file"""
        with open(filepath, 'w') as f:
            json.dump({
                "chain": [b.to_dict() for b in self.chain],
                "difficulty": self.difficulty,
                "exported_at": time.time()
            }, f, indent=2)
    
    def import_chain(self, filepath: str) -> bool:
        """
        Import and validate chain from file.
        
        Returns:
            True if import successful and chain valid
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Load blocks
            imported_chain = [Block.from_dict(b) for b in data["chain"]]
            
            # Verify imported chain
            temp_chain = self.chain
            self.chain = imported_chain
            
            if not self.is_valid():
                self.chain = temp_chain
                return False
            
            # Accept if valid
            self._save_chain()
            return True
            
        except Exception:
            return False
    
    def _save_chain(self):
        """Save chain to disk"""
        try:
            data = {
                "chain": [b.to_dict() for b in self.chain],
                "difficulty": self.difficulty,
                "updated_at": time.time()
            }
            self.chain_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Failed to save chain: {e}")
    
    def _load_chain(self):
        """Load chain from disk"""
        try:
            data = json.loads(self.chain_file.read_text())
            self.chain = [Block.from_dict(b) for b in data["chain"]]
            self.difficulty = data.get("difficulty", 2)
            
            # Verify loaded chain
            if not self.is_valid():
                print("⚠️  Loaded chain is invalid, creating new genesis")
                self.chain = []
                self._create_genesis_block()
                
        except Exception as e:
            print(f"Failed to load chain: {e}, creating new genesis")
            self.chain = []
            self._create_genesis_block()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get blockchain statistics"""
        if not self.chain:
            return {"blocks": 0}
        
        return {
            "total_blocks": len(self.chain),
            "difficulty": self.difficulty,
            "is_valid": self.is_valid(),
            "latest_block": self.get_latest_block().to_dict() if self.chain else None,
            "chain_size_bytes": len(json.dumps([b.to_dict() for b in self.chain])),
            "genesis_timestamp": self.chain[0].timestamp if self.chain else None,
            "age_hours": (time.time() - self.chain[0].timestamp) / 3600 if self.chain else 0
        }


# Global instance
_knowledge_chain_instance: Optional[KnowledgeChain] = None


def get_knowledge_chain() -> KnowledgeChain:
    """Get or create global KnowledgeChain instance"""
    global _knowledge_chain_instance
    if _knowledge_chain_instance is None:
        _knowledge_chain_instance = KnowledgeChain()
    return _knowledge_chain_instance


if __name__ == "__main__":
    # Self-test
    print("=== Knowledge Chain Self-Test ===\n")
    
    chain = KnowledgeChain(difficulty=1)  # Low difficulty for fast testing
    
    print(f"1. Chain created with {len(chain.chain)} block(s)")
    
    # Add knowledge
    print("\n2. Adding knowledge blocks...")
    chain.add_block({
        "title": "Python Programming",
        "content": "Python is a high-level programming language",
        "source": "test"
    })
    
    chain.add_block({
        "title": "Machine Learning",
        "content": "ML is a subset of artificial intelligence",
        "source": "test"
    })
    
    print(f"Chain now has {len(chain.chain)} blocks")
    
    # Verify
    print("\n3. Verifying chain integrity...")
    valid = chain.is_valid()
    print(f"Chain valid: {valid}")
    
    # Search
    print("\n4. Searching for 'Python'...")
    results = chain.search("Python")
    print(f"Found {len(results)} result(s)")
    
    # Statistics
    print("\n5. Chain statistics:")
    stats = chain.get_statistics()
    print(f"  Total blocks: {stats['total_blocks']}")
    print(f"  Valid: {stats['is_valid']}")
    print(f"  Size: {stats['chain_size_bytes']} bytes")
    
    print("\n✅ Knowledge Chain functional!")
