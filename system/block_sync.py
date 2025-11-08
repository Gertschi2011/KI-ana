"""
Block-Sync Mechanismus für P2P-Netzwerk

Synchronisiert Wissensblöcke zwischen Subminds ohne zentrale Instanz.
Verwendet Merkle Trees für effiziente Delta-Syncs.

Features:
- Block-basierte Synchronisation
- Merkle Tree für Effizienz
- Delta-Sync (nur Unterschiede)
- Conflict Resolution
- Bidirektionale Sync
"""
from __future__ import annotations
import hashlib
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, asdict
import sys

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

from p2p_connection import get_connection_manager, P2PMessage


@dataclass
class Block:
    """Represents a knowledge block."""
    id: str
    hash: str
    content: str
    metadata: Dict[str, Any]
    timestamp: float
    device_id: str
    previous_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Block':
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Block':
        return cls.from_dict(json.loads(json_str))
    
    @staticmethod
    def calculate_hash(content: str, metadata: Dict[str, Any], timestamp: float, device_id: str, previous_hash: Optional[str] = None) -> str:
        """Calculate block hash."""
        data = {
            "content": content,
            "metadata": metadata,
            "timestamp": timestamp,
            "device_id": device_id,
            "previous_hash": previous_hash
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class SyncRequest:
    """Request to sync blocks."""
    peer_id: str
    known_hashes: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SyncResponse:
    """Response with blocks to sync."""
    blocks: List[Block]
    missing_hashes: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "blocks": [b.to_dict() for b in self.blocks],
            "missing_hashes": self.missing_hashes
        }


class MerkleTree:
    """
    Merkle Tree for efficient block comparison.
    """
    
    def __init__(self, hashes: List[str]):
        self.hashes = sorted(hashes)
        self.root = self._build_tree(self.hashes)
    
    def _build_tree(self, hashes: List[str]) -> str:
        """Build Merkle tree and return root hash."""
        if not hashes:
            return hashlib.sha256(b"").hexdigest()
        
        if len(hashes) == 1:
            return hashes[0]
        
        # Build tree level by level
        current_level = hashes
        
        while len(current_level) > 1:
            next_level = []
            
            for i in range(0, len(current_level), 2):
                if i + 1 < len(current_level):
                    # Combine two hashes
                    combined = current_level[i] + current_level[i + 1]
                    next_level.append(hashlib.sha256(combined.encode()).hexdigest())
                else:
                    # Odd number, promote last hash
                    next_level.append(current_level[i])
            
            current_level = next_level
        
        return current_level[0]
    
    def get_root(self) -> str:
        """Get Merkle root hash."""
        return self.root


class BlockSyncManager:
    """
    Manages block synchronization between peers.
    
    Singleton pattern.
    """
    
    _instance: Optional['BlockSyncManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Device ID
        from submind_manager import get_submind_manager
        self.device_id = get_submind_manager().this_device_id
        
        # Local blocks storage
        self.blocks: Dict[str, Block] = {}
        self.blocks_file = Path.home() / "ki_ana" / "data" / "blocks.json"
        self.blocks_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing blocks
        self._load_blocks()
        
        # Connection manager
        self.connection_manager = get_connection_manager()
        
        # Register message handlers
        self.connection_manager.register_handler("sync_request", self._handle_sync_request)
        self.connection_manager.register_handler("sync_response", self._handle_sync_response)
        self.connection_manager.register_handler("block_push", self._handle_block_push)
        
        print(f"✅ Block-Sync Manager initialized")
        print(f"   Blocks: {len(self.blocks)}")
    
    def _load_blocks(self):
        """Load blocks from file."""
        if self.blocks_file.exists():
            try:
                data = json.loads(self.blocks_file.read_text())
                self.blocks = {
                    block_id: Block.from_dict(block_data)
                    for block_id, block_data in data.items()
                }
                print(f"📦 Loaded {len(self.blocks)} blocks from disk")
            except Exception as e:
                print(f"⚠️  Error loading blocks: {e}")
    
    def _save_blocks(self):
        """Save blocks to file."""
        try:
            data = {
                block_id: block.to_dict()
                for block_id, block in self.blocks.items()
            }
            self.blocks_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"⚠️  Error saving blocks: {e}")
    
    def add_block(self, content: str, metadata: Dict[str, Any] = None) -> Block:
        """
        Add a new block.
        
        Args:
            content: Block content
            metadata: Optional metadata
        
        Returns:
            Created block
        """
        import uuid
        
        metadata = metadata or {}
        timestamp = time.time()
        
        # Get previous hash (last block)
        previous_hash = None
        if self.blocks:
            last_block = max(self.blocks.values(), key=lambda b: b.timestamp)
            previous_hash = last_block.hash
        
        # Calculate hash
        block_hash = Block.calculate_hash(content, metadata, timestamp, self.device_id, previous_hash)
        
        # Create block
        block = Block(
            id=str(uuid.uuid4()),
            hash=block_hash,
            content=content,
            metadata=metadata,
            timestamp=timestamp,
            device_id=self.device_id,
            previous_hash=previous_hash
        )
        
        # Store block
        self.blocks[block.id] = block
        self._save_blocks()
        
        print(f"📦 Block created: {block.id[:8]}...")
        
        # Broadcast to peers
        self._broadcast_block(block)
        
        return block
    
    def _broadcast_block(self, block: Block):
        """Broadcast new block to all peers."""
        try:
            self.connection_manager.broadcast("block_push", block.to_dict())
            print(f"📡 Block broadcasted to peers")
        except Exception as e:
            print(f"⚠️  Error broadcasting block: {e}")
    
    def get_merkle_root(self) -> str:
        """Get Merkle root of all blocks."""
        hashes = [block.hash for block in self.blocks.values()]
        tree = MerkleTree(hashes)
        return tree.get_root()
    
    def get_block_hashes(self) -> List[str]:
        """Get all block hashes."""
        return [block.hash for block in self.blocks.values()]
    
    async def sync_with_peer(self, peer_id: str):
        """
        Sync blocks with a peer.
        
        Args:
            peer_id: Peer device ID
        """
        print(f"🔄 Starting sync with {peer_id}...")
        
        # Get our known hashes
        known_hashes = self.get_block_hashes()
        
        # Send sync request
        request = SyncRequest(
            peer_id=self.device_id,
            known_hashes=known_hashes
        )
        
        try:
            self.connection_manager.send_to_peer(peer_id, "sync_request", request.to_dict())
            print(f"📤 Sync request sent to {peer_id}")
        except Exception as e:
            print(f"❌ Error sending sync request: {e}")
    
    def _handle_sync_request(self, message: P2PMessage):
        """Handle sync request from peer."""
        peer_id = message.sender_id
        data = message.data
        
        print(f"📥 Sync request from {peer_id}")
        
        # Get peer's known hashes
        peer_hashes = set(data["known_hashes"])
        our_hashes = set(self.get_block_hashes())
        
        # Find blocks we have that peer doesn't
        missing_hashes = our_hashes - peer_hashes
        blocks_to_send = [
            self.blocks[block_id]
            for block_id, block in self.blocks.items()
            if block.hash in missing_hashes
        ]
        
        # Find blocks peer has that we don't
        hashes_we_need = peer_hashes - our_hashes
        
        # Send response
        response = SyncResponse(
            blocks=blocks_to_send,
            missing_hashes=list(hashes_we_need)
        )
        
        try:
            self.connection_manager.send_to_peer(peer_id, "sync_response", response.to_dict())
            print(f"📤 Sync response sent: {len(blocks_to_send)} blocks, {len(hashes_we_need)} needed")
        except Exception as e:
            print(f"❌ Error sending sync response: {e}")
    
    def _handle_sync_response(self, message: P2PMessage):
        """Handle sync response from peer."""
        peer_id = message.sender_id
        data = message.data
        
        print(f"📥 Sync response from {peer_id}")
        
        # Add received blocks
        blocks_data = data.get("blocks", [])
        for block_data in blocks_data:
            block = Block.from_dict(block_data)
            if block.id not in self.blocks:
                self.blocks[block.id] = block
                print(f"📦 Added block from {peer_id}: {block.id[:8]}...")
        
        if blocks_data:
            self._save_blocks()
        
        # Send blocks peer needs
        missing_hashes = set(data.get("missing_hashes", []))
        if missing_hashes:
            blocks_to_send = [
                block
                for block in self.blocks.values()
                if block.hash in missing_hashes
            ]
            
            for block in blocks_to_send:
                try:
                    self.connection_manager.send_to_peer(peer_id, "block_push", block.to_dict())
                except Exception as e:
                    print(f"⚠️  Error sending block: {e}")
        
        print(f"✅ Sync complete with {peer_id}")
    
    def _handle_block_push(self, message: P2PMessage):
        """Handle block push from peer."""
        peer_id = message.sender_id
        block_data = message.data
        
        block = Block.from_dict(block_data)
        
        # Check if we already have this block
        if block.id in self.blocks:
            return
        
        # Validate block hash
        expected_hash = Block.calculate_hash(
            block.content,
            block.metadata,
            block.timestamp,
            block.device_id,
            block.previous_hash
        )
        
        if expected_hash != block.hash:
            print(f"⚠️  Invalid block hash from {peer_id}")
            return
        
        # Add block
        self.blocks[block.id] = block
        self._save_blocks()
        
        print(f"📦 Received block from {peer_id}: {block.id[:8]}...")
    
    def get_blocks(self, limit: int = None) -> List[Block]:
        """Get blocks, optionally limited."""
        blocks = sorted(self.blocks.values(), key=lambda b: b.timestamp, reverse=True)
        if limit:
            blocks = blocks[:limit]
        return blocks
    
    def get_block(self, block_id: str) -> Optional[Block]:
        """Get block by ID."""
        return self.blocks.get(block_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get sync statistics."""
        return {
            "total_blocks": len(self.blocks),
            "merkle_root": self.get_merkle_root(),
            "by_device": {
                device_id: len([b for b in self.blocks.values() if b.device_id == device_id])
                for device_id in set(b.device_id for b in self.blocks.values())
            }
        }


# Singleton instance
_manager: Optional[BlockSyncManager] = None


def get_block_sync_manager() -> BlockSyncManager:
    """Get the singleton block sync manager instance."""
    global _manager
    if _manager is None:
        _manager = BlockSyncManager()
    return _manager


if __name__ == "__main__":
    # Quick test
    print("🔄 Block-Sync Manager Test\n")
    
    manager = get_block_sync_manager()
    
    # Add some test blocks
    print("📝 Adding test blocks...")
    block1 = manager.add_block("First knowledge block", {"topic": "test"})
    block2 = manager.add_block("Second knowledge block", {"topic": "test"})
    block3 = manager.add_block("Third knowledge block", {"topic": "demo"})
    
    # Get stats
    print("\n📊 Statistics:")
    stats = manager.get_stats()
    print(f"  Total blocks: {stats['total_blocks']}")
    print(f"  Merkle root: {stats['merkle_root'][:16]}...")
    print(f"  By device: {stats['by_device']}")
    
    # List blocks
    print("\n📋 Recent blocks:")
    for block in manager.get_blocks(limit=5):
        print(f"  - {block.id[:8]}... @ {block.timestamp}")
        print(f"    Content: {block.content[:50]}...")
    
    print("\n✅ Test complete!")
    print("\n💡 To sync with peers:")
    print("   await manager.sync_with_peer(peer_id)")
