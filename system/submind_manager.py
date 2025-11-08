"""
Submind Manager - Device Identity & Registry

Manages multiple devices (subminds) with unique identities, roles, and capabilities.
Each device can run independently and sync with the mother-KI.

Roles (from access_control.json):
- creator: Full access, can override, shutdown
- submind: Can learn, sync, sensor access
- user: Can interact, feedback, voice/text/gui
- sensor: Only data collection
"""
from __future__ import annotations
import json
import uuid
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class Submind:
    """Represents a submind (device) in the system."""
    id: str
    name: str
    device_type: str  # desktop, mobile, iot, sensor
    role: str  # creator, submind, user, sensor
    capabilities: List[str]
    trust_level: float  # 0.0 - 1.0
    created_at: int
    last_seen: int
    status: str  # active, inactive, revoked
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Submind':
        return cls(**data)


class SubmindManager:
    """
    Manages submind registry and device identities.
    
    Singleton pattern to ensure single registry.
    """
    
    _instance: Optional['SubmindManager'] = None
    
    # Device types and their default capabilities
    DEVICE_TYPES = {
        "desktop": ["compute", "storage", "display", "network"],
        "mobile": ["sensors", "camera", "microphone", "gps", "network"],
        "iot": ["sensors", "network"],
        "sensor": ["sensors"]
    }
    
    # Roles and their permissions (from access_control.json)
    ROLES = {
        "creator": {
            "can_override": True,
            "can_shutdown": True,
            "permissions": ["all"]
        },
        "submind": {
            "can_learn": True,
            "can_sync": True,
            "permissions": ["sensor_access", "user_interaction", "feedback_transfer"]
        },
        "user": {
            "can_interact": True,
            "can_feedback": True,
            "permissions": ["voice", "text", "gui"]
        },
        "sensor": {
            "can_sense": True,
            "permissions": ["sensor_data"]
        }
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Registry file
        self.registry_dir = Path.home() / "ki_ana" / "system" / "keys"
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.registry_dir / "submind_registry.json"
        
        # Load or create registry
        self.registry = self._load_registry()
        
        # Get or create this device's ID
        self.this_device_id = self._get_or_create_device_id()
        
        print(f"✅ Submind Manager initialized")
        print(f"   This Device: {self.this_device_id}")
        print(f"   Registry: {self.registry_file}")
    
    def _load_registry(self) -> Dict[str, Any]:
        """Load registry from file."""
        if self.registry_file.exists():
            try:
                return json.loads(self.registry_file.read_text())
            except:
                pass
        
        # Create new registry
        return {
            "version": "1.0",
            "created_at": int(time.time()),
            "subminds": [],
            "revoked": []
        }
    
    def _save_registry(self):
        """Save registry to file."""
        self.registry_file.write_text(
            json.dumps(self.registry, indent=2, ensure_ascii=False)
        )
    
    def _get_or_create_device_id(self) -> str:
        """Get or create unique device ID."""
        device_id_file = Path.home() / "ki_ana" / "data" / "device_id.txt"
        device_id_file.parent.mkdir(parents=True, exist_ok=True)
        
        if device_id_file.exists():
            return device_id_file.read_text().strip()
        
        # Generate new device ID
        device_id = str(uuid.uuid4())
        device_id_file.write_text(device_id)
        
        return device_id
    
    def register_submind(
        self,
        name: str,
        device_type: str = "desktop",
        role: str = "submind",
        capabilities: Optional[List[str]] = None,
        trust_level: float = 0.6,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Submind:
        """
        Register a new submind.
        
        Args:
            name: Human-readable name
            device_type: Type of device
            role: Role in the system
            capabilities: List of capabilities
            trust_level: Trust level (0.0 - 1.0)
            metadata: Additional metadata
        
        Returns:
            Submind object
        """
        # Validate inputs
        if device_type not in self.DEVICE_TYPES:
            raise ValueError(f"Unknown device type: {device_type}")
        
        if role not in self.ROLES:
            raise ValueError(f"Unknown role: {role}")
        
        # Default capabilities based on device type
        if capabilities is None:
            capabilities = self.DEVICE_TYPES[device_type].copy()
        
        # Create submind
        now = int(time.time())
        submind = Submind(
            id=self.this_device_id,
            name=name,
            device_type=device_type,
            role=role,
            capabilities=capabilities,
            trust_level=trust_level,
            created_at=now,
            last_seen=now,
            status="active",
            metadata=metadata or {}
        )
        
        # Add to registry
        self.registry["subminds"] = [
            s for s in self.registry["subminds"]
            if s.get("id") != submind.id
        ]
        self.registry["subminds"].append(submind.to_dict())
        self._save_registry()
        
        print(f"✅ Submind registered: {name} ({device_type})")
        
        return submind
    
    def get_submind(self, submind_id: str) -> Optional[Submind]:
        """Get submind by ID."""
        for s in self.registry["subminds"]:
            if s.get("id") == submind_id:
                return Submind.from_dict(s)
        return None
    
    def list_subminds(self, status: str = None) -> List[Submind]:
        """List all subminds, optionally filtered by status."""
        subminds = []
        for s in self.registry["subminds"]:
            submind = Submind.from_dict(s)
            if status is None or submind.status == status:
                subminds.append(submind)
        return subminds
    
    def update_last_seen(self, submind_id: str):
        """Update last seen timestamp."""
        for s in self.registry["subminds"]:
            if s.get("id") == submind_id:
                s["last_seen"] = int(time.time())
                self._save_registry()
                break
    
    def revoke_submind(self, submind_id: str):
        """Revoke a submind."""
        for s in self.registry["subminds"]:
            if s.get("id") == submind_id:
                s["status"] = "revoked"
                self.registry.setdefault("revoked", []).append(submind_id)
                self._save_registry()
                print(f"🚫 Submind revoked: {submind_id}")
                break
    
    def get_this_device(self) -> Optional[Submind]:
        """Get this device's submind entry."""
        return self.get_submind(self.this_device_id)
    
    def has_permission(self, submind_id: str, permission: str) -> bool:
        """Check if submind has a specific permission."""
        submind = self.get_submind(submind_id)
        if not submind:
            return False
        
        if submind.status != "active":
            return False
        
        role_perms = self.ROLES.get(submind.role, {}).get("permissions", [])
        
        # "all" permission grants everything
        if "all" in role_perms:
            return True
        
        return permission in role_perms
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        subminds = self.list_subminds()
        
        return {
            "total": len(subminds),
            "active": len([s for s in subminds if s.status == "active"]),
            "inactive": len([s for s in subminds if s.status == "inactive"]),
            "revoked": len([s for s in subminds if s.status == "revoked"]),
            "by_type": {
                device_type: len([s for s in subminds if s.device_type == device_type])
                for device_type in self.DEVICE_TYPES.keys()
            },
            "by_role": {
                role: len([s for s in subminds if s.role == role])
                for role in self.ROLES.keys()
            }
        }


# Singleton instance
_manager: Optional[SubmindManager] = None


def get_submind_manager() -> SubmindManager:
    """Get the singleton submind manager instance."""
    global _manager
    if _manager is None:
        _manager = SubmindManager()
    return _manager


if __name__ == "__main__":
    # Quick test
    print("🤖 Submind Manager Test\n")
    
    manager = get_submind_manager()
    
    # Register this device if not already registered
    this_device = manager.get_this_device()
    
    if not this_device:
        print("📝 Registering this device...")
        submind = manager.register_submind(
            name="Main Desktop",
            device_type="desktop",
            role="creator",
            metadata={
                "hostname": "kiana-desktop",
                "os": "Linux"
            }
        )
        print(f"✅ Registered: {submind.name}")
    else:
        print(f"✅ This device already registered: {this_device.name}")
        manager.update_last_seen(this_device.id)
    
    # List all subminds
    print("\n📋 All subminds:")
    for s in manager.list_subminds():
        print(f"  - {s.name} ({s.device_type}, {s.role})")
        print(f"    ID: {s.id}")
        print(f"    Status: {s.status}")
        print(f"    Capabilities: {', '.join(s.capabilities)}")
    
    # Stats
    print("\n📊 Statistics:")
    stats = manager.get_stats()
    print(f"  Total: {stats['total']}")
    print(f"  Active: {stats['active']}")
    print(f"  By Type: {stats['by_type']}")
    print(f"  By Role: {stats['by_role']}")
    
    # Permission check
    if this_device:
        print(f"\n🔐 Permissions for {this_device.name}:")
        for perm in ["all", "sensor_access", "user_interaction", "voice"]:
            has = manager.has_permission(this_device.id, perm)
            print(f"  {perm}: {'✅' if has else '❌'}")
    
    print("\n✅ Test complete!")
