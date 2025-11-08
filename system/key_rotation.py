"""
Key Rotation System für KI_ana

Features:
- Automatic Key Rotation (30 Tage)
- Graceful Key Transition
- Key History Management
- Emergency Key Revocation
"""
from __future__ import annotations
import time
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import sys

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

try:
    from nacl.public import PrivateKey, PublicKey
    from nacl.encoding import Base64Encoder
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False


@dataclass
class KeyInfo:
    """Key information."""
    key_id: str
    created_at: float
    expires_at: float
    status: str  # active, transitioning, revoked
    public_key: str
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at
    
    def to_dict(self) -> Dict:
        return asdict(self)


class KeyRotationService:
    """
    Key Rotation Service.
    
    Manages automatic key rotation for encryption keys.
    """
    
    _instance: Optional['KeyRotationService'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        if not NACL_AVAILABLE:
            print("❌ PyNaCl not available")
            self._initialized = True
            return
        
        self._initialized = True
        
        # Device ID
        from submind_manager import get_submind_manager
        self.device_id = get_submind_manager().this_device_id
        
        # Keys directory
        self.keys_dir = Path.home() / "ki_ana" / "system" / "keys"
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        
        # Key history file
        self.history_file = self.keys_dir / "key_history.json"
        
        # Key history
        self.key_history: List[KeyInfo] = []
        self._load_history()
        
        # Rotation policy (30 days)
        self.rotation_interval = 30 * 24 * 60 * 60  # 30 days in seconds
        
        # Transition period (7 days)
        self.transition_period = 7 * 24 * 60 * 60  # 7 days
        
        print(f"✅ Key Rotation Service initialized")
    
    def _load_history(self):
        """Load key history from file."""
        if self.history_file.exists():
            try:
                data = json.loads(self.history_file.read_text())
                self.key_history = [KeyInfo(**item) for item in data]
                print(f"📜 Loaded {len(self.key_history)} key(s) from history")
            except Exception as e:
                print(f"⚠️  Error loading key history: {e}")
    
    def _save_history(self):
        """Save key history to file."""
        try:
            data = [key.to_dict() for key in self.key_history]
            self.history_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"⚠️  Error saving key history: {e}")
    
    def get_active_key(self) -> Optional[KeyInfo]:
        """Get currently active key."""
        for key in self.key_history:
            if key.status == "active" and not key.is_expired():
                return key
        return None
    
    def check_rotation_needed(self) -> bool:
        """Check if key rotation is needed."""
        active_key = self.get_active_key()
        
        if not active_key:
            print("⚠️  No active key found, rotation needed")
            return True
        
        # Check if key is close to expiration
        time_until_expiry = active_key.expires_at - time.time()
        
        if time_until_expiry < self.transition_period:
            print(f"⚠️  Key expires in {time_until_expiry/86400:.1f} days, rotation needed")
            return True
        
        return False
    
    def rotate_keys(self) -> KeyInfo:
        """
        Rotate encryption keys.
        
        Creates new key pair and transitions from old key.
        """
        print("🔄 Starting key rotation...")
        
        # Generate new key pair
        private_key = PrivateKey.generate()
        public_key = private_key.public_key
        
        # Generate key ID
        key_id = f"key_{int(time.time())}"
        
        # Save new keys
        private_file = self.keys_dir / f"{self.device_id}_messaging_private_{key_id}.key"
        public_file = self.keys_dir / f"{self.device_id}_messaging_public_{key_id}.key"
        
        private_file.write_bytes(bytes(private_key))
        public_file.write_bytes(bytes(public_key))
        
        # Secure permissions
        import os
        os.chmod(private_file, 0o600)
        
        # Create key info
        key_info = KeyInfo(
            key_id=key_id,
            created_at=time.time(),
            expires_at=time.time() + self.rotation_interval,
            status="transitioning",
            public_key=public_key.encode(encoder=Base64Encoder).decode()
        )
        
        # Mark old key as transitioning
        active_key = self.get_active_key()
        if active_key:
            active_key.status = "transitioning"
            print(f"📝 Old key {active_key.key_id} marked as transitioning")
        
        # Add new key to history
        self.key_history.append(key_info)
        self._save_history()
        
        print(f"✅ New key generated: {key_id}")
        print(f"   Public Key: {key_info.public_key[:32]}...")
        print(f"   Expires: {time.ctime(key_info.expires_at)}")
        
        return key_info
    
    def activate_new_key(self, key_id: str):
        """Activate new key after transition period."""
        for key in self.key_history:
            if key.key_id == key_id:
                key.status = "active"
                print(f"✅ Key {key_id} activated")
                
                # Revoke old keys
                for old_key in self.key_history:
                    if old_key.key_id != key_id and old_key.status != "revoked":
                        old_key.status = "revoked"
                        print(f"🔒 Old key {old_key.key_id} revoked")
                
                self._save_history()
                return
        
        print(f"⚠️  Key {key_id} not found")
    
    def revoke_key(self, key_id: str, reason: str = "Manual revocation"):
        """Emergency key revocation."""
        for key in self.key_history:
            if key.key_id == key_id:
                key.status = "revoked"
                print(f"🚨 Key {key_id} revoked: {reason}")
                self._save_history()
                return
        
        print(f"⚠️  Key {key_id} not found")
    
    def cleanup_old_keys(self, keep_days: int = 90):
        """Cleanup old revoked keys."""
        cutoff = time.time() - (keep_days * 24 * 60 * 60)
        
        removed = []
        for key in self.key_history[:]:
            if key.status == "revoked" and key.created_at < cutoff:
                # Remove key files
                private_file = self.keys_dir / f"{self.device_id}_messaging_private_{key.key_id}.key"
                public_file = self.keys_dir / f"{self.device_id}_messaging_public_{key.key_id}.key"
                
                private_file.unlink(missing_ok=True)
                public_file.unlink(missing_ok=True)
                
                self.key_history.remove(key)
                removed.append(key.key_id)
        
        if removed:
            print(f"🧹 Cleaned up {len(removed)} old key(s)")
            self._save_history()
        
        return removed


# Singleton
_service: Optional[KeyRotationService] = None


def get_key_rotation_service() -> KeyRotationService:
    """Get singleton key rotation service."""
    global _service
    if _service is None:
        _service = KeyRotationService()
    return _service


if __name__ == "__main__":
    print("🔑 Key Rotation Service Test\n")
    
    if not NACL_AVAILABLE:
        print("❌ PyNaCl not installed")
        exit(1)
    
    service = get_key_rotation_service()
    
    # Check if rotation needed
    print("1️⃣ Checking if rotation needed...")
    needs_rotation = service.check_rotation_needed()
    print(f"   Rotation needed: {needs_rotation}")
    
    # Get active key
    print("\n2️⃣ Getting active key...")
    active_key = service.get_active_key()
    if active_key:
        print(f"   Key ID: {active_key.key_id}")
        print(f"   Status: {active_key.status}")
        print(f"   Expires: {time.ctime(active_key.expires_at)}")
    else:
        print("   No active key found")
    
    # Simulate rotation (commented out for safety)
    # print("\n3️⃣ Simulating key rotation...")
    # new_key = service.rotate_keys()
    # print(f"   New key: {new_key.key_id}")
    
    print("\n✅ Key Rotation Service test complete!")
    print("\n💡 To rotate keys:")
    print("   service = get_key_rotation_service()")
    print("   new_key = service.rotate_keys()")
    print("   service.activate_new_key(new_key.key_id)")
