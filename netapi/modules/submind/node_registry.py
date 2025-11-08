"""
Node Registry
Tracks all Sub-Mind nodes in the network
Phase 8 - Sub-Minds
"""
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from enum import Enum


class NodeType(str, Enum):
    MOTHER = "mother"
    CHILD = "child"
    EDGE = "edge"


class NodeRegistry:
    """Manages registry of all network nodes"""
    
    def __init__(self):
        self.registry_file = Path("/home/kiana/ki_ana/data/nodes.json")
        self.config = self._load_config()
        self.nodes = self._load_registry()
        
        # Ensure mother node exists
        self._ensure_mother_node()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load submind config"""
        config_file = Path("/home/kiana/ki_ana/data/submind_config.json")
        
        if not config_file.exists():
            return {}
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        """Load node registry"""
        if not self.registry_file.exists():
            return {}
        
        try:
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def _save_registry(self):
        """Save node registry"""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(self.nodes, f, indent=2)
    
    def _ensure_mother_node(self):
        """Ensure mother node is registered"""
        mother_id = "mother_node_main"
        
        if mother_id not in self.nodes:
            self.register_node(
                node_id=mother_id,
                node_type=NodeType.MOTHER,
                address="localhost:8000",
                specialization=None,
                capabilities=["full_ai", "consensus", "signing"]
            )
    
    def register_node(
        self,
        node_id: str,
        node_type: NodeType,
        address: str,
        specialization: Optional[str] = None,
        capabilities: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Register a node"""
        timestamp = int(time.time())
        
        node = {
            "node_id": node_id,
            "type": node_type.value,
            "specialization": specialization,
            "address": address,
            "capabilities": capabilities or [],
            "registered_at": timestamp,
            "last_seen": timestamp,
            "trust_score": 5.0,  # Starting trust
            "status": "active"
        }
        
        self.nodes[node_id] = node
        self._save_registry()
        
        return node
    
    def update_node_heartbeat(self, node_id: str) -> bool:
        """Update node last_seen timestamp"""
        if node_id not in self.nodes:
            return False
        
        self.nodes[node_id]["last_seen"] = int(time.time())
        self._save_registry()
        
        return True
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node info"""
        return self.nodes.get(node_id)
    
    def list_nodes(
        self,
        node_type: Optional[NodeType] = None,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """List all nodes"""
        nodes = list(self.nodes.values())
        
        # Filter by type
        if node_type:
            nodes = [n for n in nodes if n['type'] == node_type.value]
        
        # Filter by active
        if active_only:
            timeout = 600  # 10 minutes
            cutoff = int(time.time()) - timeout
            nodes = [n for n in nodes if n.get('last_seen', 0) > cutoff]
        
        return nodes
    
    def update_trust_score(
        self,
        node_id: str,
        delta: float
    ) -> float:
        """Update node trust score"""
        if node_id not in self.nodes:
            return 0.0
        
        current = self.nodes[node_id].get("trust_score", 5.0)
        new_score = max(0.0, min(10.0, current + delta))
        
        self.nodes[node_id]["trust_score"] = new_score
        self._save_registry()
        
        return new_score
    
    def get_network_stats(self) -> Dict[str, Any]:
        """Get network statistics"""
        active_nodes = self.list_nodes(active_only=True)
        
        by_type = {}
        for node in active_nodes:
            node_type = node['type']
            by_type[node_type] = by_type.get(node_type, 0) + 1
        
        avg_trust = (
            sum(n.get('trust_score', 5.0) for n in active_nodes) / len(active_nodes)
            if active_nodes else 0
        )
        
        return {
            "total_nodes": len(self.nodes),
            "active_nodes": len(active_nodes),
            "by_type": by_type,
            "average_trust": round(avg_trust, 2),
            "specializations": list(set(
                n.get('specialization') for n in active_nodes
                if n.get('specialization')
            ))
        }


# Singleton
_registry = None


def get_node_registry() -> NodeRegistry:
    """Get singleton node registry"""
    global _registry
    if _registry is None:
        _registry = NodeRegistry()
    return _registry


if __name__ == "__main__":
    # Test
    registry = NodeRegistry()
    
    # Register a child node
    child = registry.register_node(
        node_id="child_vision_01",
        node_type=NodeType.CHILD,
        address="192.168.1.100:9001",
        specialization="vision_node",
        capabilities=["image_processing", "object_detection"]
    )
    
    print("Registered node:", json.dumps(child, indent=2))
    
    # Get stats
    stats = registry.get_network_stats()
    print("\nNetwork stats:", json.dumps(stats, indent=2))
