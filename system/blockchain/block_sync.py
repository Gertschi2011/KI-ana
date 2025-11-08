"""
BlockSyncManager - Blockchain Synchronization Manager
Handles peer discovery, block synchronization, and chain validation
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json
import hashlib
import time
from datetime import datetime


class BlockSyncManager:
    """Manages blockchain synchronization across nodes"""
    
    def __init__(self, chain_dir: Path | str = None):
        self.chain_dir = Path(chain_dir) if chain_dir else Path(__file__).parent.parent / "chain"
        self.chain_dir.mkdir(parents=True, exist_ok=True)
        self.blocks_cache: Dict[str, Dict[str, Any]] = {}
        self.peers: List[str] = []
        
    def get_block(self, block_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a block by ID
        
        Args:
            block_id: Block identifier (hash or filename without .json)
            
        Returns:
            Block data dictionary or None if not found
        """
        # Check cache first
        if block_id in self.blocks_cache:
            return self.blocks_cache[block_id]
            
        # Load from disk
        block_file = self.chain_dir / f"{block_id}.json"
        if not block_file.exists():
            return None
            
        try:
            with open(block_file, 'r', encoding='utf-8') as f:
                block_data = json.load(f)
            
            # Cache it
            self.blocks_cache[block_id] = block_data
            return block_data
        except Exception as e:
            print(f"Error loading block {block_id}: {e}")
            return None
    
    def sync_chain(self, peer_url: str = None) -> Tuple[bool, str]:
        """
        Synchronize blockchain with peers
        
        Args:
            peer_url: Optional specific peer to sync with
            
        Returns:
            (success, message) tuple
        """
        try:
            # Load local chain
            local_blocks = self._load_local_chain()
            local_height = len(local_blocks)
            
            if not peer_url and not self.peers:
                return True, f"No peers configured, local chain height: {local_height}"
            
            # For now, just validate local chain
            # TODO: Implement actual P2P sync when P2P messaging is available
            is_valid, msg = self.validate_blocks()
            
            if is_valid:
                return True, f"Local chain validated, height: {local_height}"
            else:
                return False, f"Chain validation failed: {msg}"
                
        except Exception as e:
            return False, f"Sync failed: {str(e)}"
    
    def validate_blocks(self) -> Tuple[bool, str]:
        """
        Validate all blocks in the local chain
        
        Returns:
            (is_valid, message) tuple
        """
        blocks = self._load_local_chain()
        
        if not blocks:
            return False, "No blocks found"
        
        # Validate genesis block
        genesis = blocks[0]
        if not self._validate_genesis(genesis):
            return False, "Invalid genesis block"
        
        # Validate chain integrity
        for i in range(1, len(blocks)):
            current = blocks[i]
            previous = blocks[i-1]
            
            # Check previous hash reference
            if current.get('previous_hash') != previous.get('hash'):
                return False, f"Block {i} previous_hash mismatch"
            
            # Validate current block hash
            if not self._validate_block_hash(current):
                return False, f"Block {i} hash invalid"
        
        return True, f"Chain valid, {len(blocks)} blocks"
    
    def add_peer(self, peer_url: str) -> bool:
        """Add a peer node for synchronization"""
        if peer_url not in self.peers:
            self.peers.append(peer_url)
            return True
        return False
    
    def remove_peer(self, peer_url: str) -> bool:
        """Remove a peer node"""
        if peer_url in self.peers:
            self.peers.remove(peer_url)
            return True
        return False
    
    def get_chain_height(self) -> int:
        """Get current blockchain height"""
        return len(self._load_local_chain())
    
    def get_latest_block(self) -> Optional[Dict[str, Any]]:
        """Get the most recent block"""
        blocks = self._load_local_chain()
        return blocks[-1] if blocks else None
    
    def _load_local_chain(self) -> List[Dict[str, Any]]:
        """Load all blocks from local chain directory"""
        blocks = []
        
        if not self.chain_dir.exists():
            return blocks
        
        # Load all JSON files
        for block_file in sorted(self.chain_dir.glob("*.json")):
            try:
                with open(block_file, 'r', encoding='utf-8') as f:
                    block_data = json.load(f)
                blocks.append(block_data)
            except Exception as e:
                print(f"Error loading {block_file}: {e}")
                continue
        
        # Sort by timestamp
        blocks.sort(key=lambda b: b.get('timestamp', 0))
        return blocks
    
    def _validate_genesis(self, block: Dict[str, Any]) -> bool:
        """Validate genesis block"""
        required_fields = ['id', 'timestamp', 'data', 'hash']
        for field in required_fields:
            if field not in block:
                return False
        
        # Genesis block should have no previous_hash or previous_hash = "0"
        prev_hash = block.get('previous_hash', '0')
        return prev_hash == '0' or prev_hash == '' or prev_hash is None
    
    def _validate_block_hash(self, block: Dict[str, Any]) -> bool:
        """Validate block hash integrity"""
        stored_hash = block.get('hash')
        if not stored_hash:
            return False
        
        # Recalculate hash
        block_copy = dict(block)
        block_copy.pop('hash', None)
        block_copy.pop('signature', None)  # Don't include signature in hash
        
        # Canonical JSON
        canonical_json = json.dumps(block_copy, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        calculated_hash = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
        
        return stored_hash == calculated_hash
    
    def create_block(self, data: Dict[str, Any], previous_block: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new block
        
        Args:
            data: Block data/content
            previous_block: Previous block in chain (None for genesis)
            
        Returns:
            New block dictionary
        """
        if previous_block is None:
            previous_hash = "0"
            block_id = "genesis"
        else:
            previous_hash = previous_block.get('hash', '')
            block_id = f"block_{int(time.time())}"
        
        block = {
            'id': block_id,
            'timestamp': int(time.time()),
            'data': data,
            'previous_hash': previous_hash,
            'created_at': datetime.utcnow().isoformat() + 'Z'
        }
        
        # Calculate hash
        canonical_json = json.dumps(block, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        block['hash'] = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
        
        return block
    
    def save_block(self, block: Dict[str, Any]) -> bool:
        """Save block to local chain"""
        try:
            block_id = block.get('id', f"block_{int(time.time())}")
            block_file = self.chain_dir / f"{block_id}.json"
            
            with open(block_file, 'w', encoding='utf-8') as f:
                json.dump(block, f, indent=2, ensure_ascii=False)
            
            # Update cache
            self.blocks_cache[block_id] = block
            return True
        except Exception as e:
            print(f"Error saving block: {e}")
            return False
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status"""
        return {
            'chain_height': self.get_chain_height(),
            'peers_count': len(self.peers),
            'peers': self.peers,
            'last_sync': int(time.time()),
            'is_syncing': False  # TODO: Implement actual sync status
        }


# Convenience function for quick access
def get_block_sync_manager() -> BlockSyncManager:
    """Get a singleton BlockSyncManager instance"""
    if not hasattr(get_block_sync_manager, '_instance'):
        get_block_sync_manager._instance = BlockSyncManager()
    return get_block_sync_manager._instance
