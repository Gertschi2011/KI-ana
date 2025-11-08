"""
Public Node Registry für KI_ana
Opt-in globales Netzwerk
"""
from pathlib import Path
import time
import json

class NodeRegistry:
    def __init__(self):
        self.nodes = {}
        self.registry_file = Path.home() / "ki_ana" / "data" / "node_registry.json"
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"✅ Node Registry initialized")
    
    def register_node(self, node_id: str, info: dict):
        self.nodes[node_id] = {**info, "last_seen": time.time()}
        self._save()
        print(f"✅ Node registered: {node_id[:8]}...")
    
    def _save(self):
        self.registry_file.write_text(json.dumps(self.nodes, indent=2))

_registry = None
def get_node_registry():
    global _registry
    if _registry is None:
        _registry = NodeRegistry()
    return _registry
