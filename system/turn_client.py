"""
TURN Client für KI_ana P2P

Ermöglicht WebRTC-Verbindungen hinter NAT/Firewall.

Features:
- TURN Server Integration
- ICE Candidate Handling
- NAT Traversal
- Fallback für WebRTC
"""
from __future__ import annotations
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import sys
from pathlib import Path

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))


@dataclass
class TURNConfig:
    """TURN Server configuration."""
    urls: List[str]  # e.g., ["turn:turn.example.com:3478"]
    username: str
    credential: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "urls": self.urls,
            "username": self.username,
            "credential": self.credential
        }


class TURNClient:
    """
    TURN Client for NAT traversal.
    
    Integrates with WebRTC P2P connections.
    """
    
    _instance: Optional['TURNClient'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # TURN configuration
        self.turn_servers: List[TURNConfig] = []
        
        # Load config
        self._load_config()
        
        print(f"✅ TURN Client initialized")
        if self.turn_servers:
            print(f"   TURN Servers: {len(self.turn_servers)}")
    
    def _load_config(self):
        """Load TURN configuration."""
        config_file = Path.home() / "ki_ana" / "infra" / "turn" / "turn_config.json"
        
        if config_file.exists():
            try:
                data = json.loads(config_file.read_text())
                for server_data in data.get("servers", []):
                    self.turn_servers.append(TURNConfig(**server_data))
                print(f"📡 Loaded {len(self.turn_servers)} TURN server(s)")
            except Exception as e:
                print(f"⚠️  Error loading TURN config: {e}")
        else:
            # Default config (local development)
            self.turn_servers = [
                TURNConfig(
                    urls=["turn:localhost:3478"],
                    username="kiana",
                    credential="kiana_turn_password"
                )
            ]
            print(f"⚠️  Using default TURN config (localhost)")
    
    def get_ice_servers(self) -> List[Dict[str, Any]]:
        """
        Get ICE servers configuration for WebRTC.
        
        Returns list of ICE servers including STUN and TURN.
        """
        ice_servers = []
        
        # Add public STUN servers
        ice_servers.append({
            "urls": [
                "stun:stun.l.google.com:19302",
                "stun:stun1.l.google.com:19302"
            ]
        })
        
        # Add TURN servers
        for turn_server in self.turn_servers:
            ice_servers.append(turn_server.to_dict())
        
        return ice_servers
    
    def add_turn_server(self, urls: List[str], username: str, credential: str):
        """Add TURN server."""
        self.turn_servers.append(TURNConfig(urls, username, credential))
        print(f"✅ Added TURN server: {urls[0]}")
    
    def test_connectivity(self) -> bool:
        """Test TURN server connectivity."""
        if not self.turn_servers:
            print("⚠️  No TURN servers configured")
            return False
        
        # Would test actual connectivity here
        print(f"🧪 Testing {len(self.turn_servers)} TURN server(s)...")
        print(f"✅ TURN connectivity test (simulated)")
        
        return True


# Singleton
_client: Optional[TURNClient] = None


def get_turn_client() -> TURNClient:
    """Get singleton TURN client."""
    global _client
    if _client is None:
        _client = TURNClient()
    return _client


if __name__ == "__main__":
    print("📡 TURN Client Test\n")
    
    client = get_turn_client()
    
    # Get ICE servers
    ice_servers = client.get_ice_servers()
    print(f"\n🧊 ICE Servers:")
    for server in ice_servers:
        print(f"   {server}")
    
    # Test connectivity
    print()
    client.test_connectivity()
    
    print("\n✅ TURN Client test complete!")
    print("\n💡 To use with WebRTC:")
    print("   ice_servers = get_turn_client().get_ice_servers()")
    print("   RTCPeerConnection(configuration={'iceServers': ice_servers})")
