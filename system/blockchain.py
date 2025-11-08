"""
Dezentrale Blockchain für KI_ana P2P-Netzwerk

Erweitert Block-Sync um Blockchain-Features:
- Chain Validation
- Consensus Mechanismus
- Fork Resolution
- Byzantine Fault Tolerance (Basic)

Features:
- Proof of Authority (PoA) Consensus
- Chain Verification
- Fork Detection & Resolution
- Longest Chain Rule
- Block Propagation
"""
from __future__ import annotations
import hashlib
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import sys

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

from block_sync import Block, get_block_sync_manager
from submind_manager import get_submind_manager


@dataclass
class ChainStats:
    """Blockchain statistics."""
    length: int
    head_hash: str
    genesis_hash: str
    total_devices: int
    is_valid: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "length": self.length,
            "head_hash": self.head_hash,
            "genesis_hash": self.genesis_hash,
            "total_devices": self.total_devices,
            "is_valid": self.is_valid
        }


class Blockchain:
    """
    Dezentrale Blockchain für P2P-Netzwerk.
    
    Singleton pattern.
    """
    
    _instance: Optional['Blockchain'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Block sync manager
        self.block_manager = get_block_sync_manager()
        
        # Submind manager for authority
        self.submind_manager = get_submind_manager()
        
        # Chain cache
        self.chain_cache: Optional[List[Block]] = None
        self.chain_valid: Optional[bool] = None
        
        print(f"✅ Blockchain initialized")
    
    def get_chain(self, rebuild: bool = False) -> List[Block]:
        """
        Get the blockchain in order.
        
        Args:
            rebuild: Force rebuild of chain cache
        
        Returns:
            List of blocks in chain order
        """
        if self.chain_cache and not rebuild:
            return self.chain_cache
        
        # Build chain from blocks
        blocks = list(self.block_manager.blocks.values())
        
        if not blocks:
            self.chain_cache = []
            return []
        
        # Find genesis block (no previous_hash)
        genesis = [b for b in blocks if b.previous_hash is None]
        
        if not genesis:
            # No genesis, use oldest block
            genesis = [min(blocks, key=lambda b: b.timestamp)]
        
        # Build chain
        chain = []
        current = genesis[0]
        chain.append(current)
        
        # Follow the chain
        used_blocks = {current.hash}
        
        while True:
            # Find next block
            next_blocks = [
                b for b in blocks
                if b.previous_hash == current.hash and b.hash not in used_blocks
            ]
            
            if not next_blocks:
                break
            
            # If multiple, choose by timestamp (oldest first)
            current = min(next_blocks, key=lambda b: b.timestamp)
            chain.append(current)
            used_blocks.add(current.hash)
        
        self.chain_cache = chain
        return chain
    
    def validate_chain(self) -> Tuple[bool, Optional[str]]:
        """
        Validate the entire blockchain.
        
        Returns:
            (is_valid, error_message)
        """
        chain = self.get_chain()
        
        if not chain:
            return True, None
        
        # Validate genesis
        genesis = chain[0]
        if genesis.previous_hash is not None:
            return False, "Genesis block has previous_hash"
        
        # Validate each block
        for i, block in enumerate(chain):
            # Validate hash
            expected_hash = Block.calculate_hash(
                block.content,
                block.metadata,
                block.timestamp,
                block.device_id,
                block.previous_hash
            )
            
            if expected_hash != block.hash:
                return False, f"Invalid hash at block {i}"
            
            # Validate chain link
            if i > 0:
                prev_block = chain[i - 1]
                if block.previous_hash != prev_block.hash:
                    return False, f"Broken chain at block {i}"
            
            # Validate timestamp (should be after previous)
            if i > 0:
                prev_block = chain[i - 1]
                if block.timestamp < prev_block.timestamp:
                    return False, f"Invalid timestamp at block {i}"
        
        self.chain_valid = True
        return True, None
    
    def get_head(self) -> Optional[Block]:
        """Get the head (latest) block of the chain."""
        chain = self.get_chain()
        return chain[-1] if chain else None
    
    def get_genesis(self) -> Optional[Block]:
        """Get the genesis (first) block of the chain."""
        chain = self.get_chain()
        return chain[0] if chain else None
    
    def get_chain_length(self) -> int:
        """Get the length of the blockchain."""
        return len(self.get_chain())
    
    def detect_forks(self) -> List[List[Block]]:
        """
        Detect forks in the blockchain.
        
        Returns:
            List of fork chains
        """
        blocks = list(self.block_manager.blocks.values())
        
        # Find blocks with same previous_hash (forks)
        prev_hash_map: Dict[str, List[Block]] = {}
        
        for block in blocks:
            if block.previous_hash:
                prev_hash_map.setdefault(block.previous_hash, []).append(block)
        
        # Find forks (more than one block with same previous)
        forks = []
        for prev_hash, blocks_list in prev_hash_map.items():
            if len(blocks_list) > 1:
                forks.append(blocks_list)
        
        return forks
    
    def resolve_forks(self) -> bool:
        """
        Resolve forks using longest chain rule.
        
        Returns:
            True if forks were resolved
        """
        forks = self.detect_forks()
        
        if not forks:
            return False
        
        print(f"🔀 Detected {len(forks)} fork(s)")
        
        # For each fork, keep the block from the longest chain
        for fork_blocks in forks:
            # Build chains for each fork
            chains = []
            for fork_block in fork_blocks:
                # Build chain from this fork
                chain = self._build_chain_from_block(fork_block)
                chains.append((len(chain), fork_block))
            
            # Keep longest chain
            chains.sort(reverse=True)
            longest_length, winning_block = chains[0]
            
            # Remove other fork blocks
            for _, fork_block in chains[1:]:
                if fork_block.id in self.block_manager.blocks:
                    del self.block_manager.blocks[fork_block.id]
                    print(f"🗑️  Removed fork block: {fork_block.id[:8]}...")
        
        # Rebuild chain cache
        self.get_chain(rebuild=True)
        
        return True
    
    def _build_chain_from_block(self, start_block: Block) -> List[Block]:
        """Build chain forward from a block."""
        chain = [start_block]
        blocks = list(self.block_manager.blocks.values())
        
        current = start_block
        used = {current.hash}
        
        while True:
            next_blocks = [
                b for b in blocks
                if b.previous_hash == current.hash and b.hash not in used
            ]
            
            if not next_blocks:
                break
            
            current = min(next_blocks, key=lambda b: b.timestamp)
            chain.append(current)
            used.add(current.hash)
        
        return chain
    
    def validate_block_authority(self, block: Block) -> bool:
        """
        Validate that the block creator has authority.
        
        Uses Proof of Authority (PoA) - only trusted devices can create blocks.
        
        Args:
            block: Block to validate
        
        Returns:
            True if authorized
        """
        # Get device info
        device = self.submind_manager.get_submind(block.device_id)
        
        if not device:
            # Unknown device - reject
            return False
        
        # Check trust level
        if device.trust_level < 0.5:
            # Low trust - reject
            return False
        
        # Check role
        if device.role not in ["creator", "submind"]:
            # Only creator and submind can create blocks
            return False
        
        return True
    
    def get_stats(self) -> ChainStats:
        """Get blockchain statistics."""
        chain = self.get_chain()
        
        if not chain:
            return ChainStats(
                length=0,
                head_hash="",
                genesis_hash="",
                total_devices=0,
                is_valid=True
            )
        
        # Validate chain
        is_valid, _ = self.validate_chain()
        
        # Count unique devices
        devices = set(b.device_id for b in chain)
        
        return ChainStats(
            length=len(chain),
            head_hash=chain[-1].hash,
            genesis_hash=chain[0].hash,
            total_devices=len(devices),
            is_valid=is_valid
        )
    
    def export_chain(self, output_file: Path = None) -> str:
        """
        Export blockchain to JSON.
        
        Args:
            output_file: Optional file to write to
        
        Returns:
            JSON string
        """
        chain = self.get_chain()
        
        data = {
            "version": "1.0",
            "exported_at": time.time(),
            "chain_length": len(chain),
            "blocks": [block.to_dict() for block in chain]
        }
        
        json_str = json.dumps(data, indent=2)
        
        if output_file:
            output_file.write_text(json_str)
            print(f"✅ Chain exported to {output_file}")
        
        return json_str
    
    def import_chain(self, json_str: str, merge: bool = True) -> bool:
        """
        Import blockchain from JSON.
        
        Args:
            json_str: JSON string
            merge: If True, merge with existing chain
        
        Returns:
            True if successful
        """
        try:
            data = json.loads(json_str)
            blocks_data = data.get("blocks", [])
            
            if not merge:
                # Clear existing blocks
                self.block_manager.blocks.clear()
            
            # Import blocks
            for block_data in blocks_data:
                block = Block.from_dict(block_data)
                
                # Validate block
                if not self.validate_block_authority(block):
                    print(f"⚠️  Skipping unauthorized block: {block.id[:8]}...")
                    continue
                
                # Add block
                self.block_manager.blocks[block.id] = block
            
            # Rebuild chain
            self.get_chain(rebuild=True)
            
            # Validate
            is_valid, error = self.validate_chain()
            if not is_valid:
                print(f"⚠️  Imported chain is invalid: {error}")
                return False
            
            print(f"✅ Imported {len(blocks_data)} blocks")
            return True
        
        except Exception as e:
            print(f"❌ Import failed: {e}")
            return False


# Singleton instance
_blockchain: Optional[Blockchain] = None


def get_blockchain() -> Blockchain:
    """Get the singleton blockchain instance."""
    global _blockchain
    if _blockchain is None:
        _blockchain = Blockchain()
    return _blockchain


if __name__ == "__main__":
    # Quick test
    print("⛓️  Blockchain Test\n")
    
    blockchain = get_blockchain()
    
    # Add some blocks
    print("📝 Adding test blocks...")
    manager = blockchain.block_manager
    
    block1 = manager.add_block("Genesis block", {"type": "genesis"})
    time.sleep(0.1)
    block2 = manager.add_block("Second block", {"type": "data"})
    time.sleep(0.1)
    block3 = manager.add_block("Third block", {"type": "data"})
    
    # Get chain
    print("\n⛓️  Blockchain:")
    chain = blockchain.get_chain()
    for i, block in enumerate(chain):
        print(f"  {i}. {block.id[:8]}... @ {block.timestamp}")
        print(f"     Hash: {block.hash[:16]}...")
        print(f"     Prev: {block.previous_hash[:16] if block.previous_hash else 'None'}...")
    
    # Validate
    print("\n✅ Validating chain...")
    is_valid, error = blockchain.validate_chain()
    if is_valid:
        print("✅ Chain is valid!")
    else:
        print(f"❌ Chain is invalid: {error}")
    
    # Stats
    print("\n📊 Statistics:")
    stats = blockchain.get_stats()
    print(f"  Length: {stats.length}")
    print(f"  Head: {stats.head_hash[:16]}...")
    print(f"  Genesis: {stats.genesis_hash[:16]}...")
    print(f"  Devices: {stats.total_devices}")
    print(f"  Valid: {stats.is_valid}")
    
    # Detect forks
    print("\n🔀 Checking for forks...")
    forks = blockchain.detect_forks()
    if forks:
        print(f"⚠️  Found {len(forks)} fork(s)")
    else:
        print("✅ No forks detected")
    
    print("\n✅ Test complete!")
