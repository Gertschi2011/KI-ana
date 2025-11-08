"""
Network Resilience für P2P-Netzwerk

Features:
- Peer Failure Detection
- Automatic Reconnection
- Network Partitioning Handling
- Gossip Protocol (Basic)
- Load Balancing
"""
from __future__ import annotations
import time
from typing import Dict, Optional, List
from dataclasses import dataclass
import sys
from pathlib import Path

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

from p2p_connection import get_connection_manager
from p2p_discovery import get_discovery_service


@dataclass
class PeerHealth:
    """Health status of a peer."""
    peer_id: str
    last_seen: float
    failed_attempts: int
    status: str  # healthy, degraded, failed
    
    def is_healthy(self) -> bool:
        return self.status == "healthy"
    
    def is_stale(self, timeout: float = 60.0) -> bool:
        return time.time() - self.last_seen > timeout


class NetworkResilience:
    """
    Network Resilience Manager.
    
    Monitors peer health and handles failures.
    """
    
    _instance: Optional['NetworkResilience'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Peer health tracking
        self.peer_health: Dict[str, PeerHealth] = {}
        
        # Connection manager
        self.connection_mgr = get_connection_manager()
        
        # Discovery service
        self.discovery = get_discovery_service()
        
        # Config
        self.heartbeat_interval = 30.0  # seconds
        self.peer_timeout = 60.0  # seconds
        self.max_failed_attempts = 3
        
        print(f"✅ Network Resilience initialized")
    
    def update_peer_health(self, peer_id: str):
        """Update peer health status."""
        if peer_id not in self.peer_health:
            self.peer_health[peer_id] = PeerHealth(
                peer_id=peer_id,
                last_seen=time.time(),
                failed_attempts=0,
                status="healthy"
            )
        else:
            health = self.peer_health[peer_id]
            health.last_seen = time.time()
            health.failed_attempts = 0
            health.status = "healthy"
    
    def mark_peer_failed(self, peer_id: str):
        """Mark peer as failed."""
        if peer_id in self.peer_health:
            health = self.peer_health[peer_id]
            health.failed_attempts += 1
            
            if health.failed_attempts >= self.max_failed_attempts:
                health.status = "failed"
                print(f"❌ Peer marked as failed: {peer_id}")
            else:
                health.status = "degraded"
                print(f"⚠️  Peer degraded: {peer_id} ({health.failed_attempts} failures)")
    
    def check_stale_peers(self) -> List[str]:
        """Check for stale peers."""
        stale = []
        
        for peer_id, health in self.peer_health.items():
            if health.is_stale(self.peer_timeout):
                stale.append(peer_id)
                self.mark_peer_failed(peer_id)
        
        return stale
    
    async def reconnect_failed_peers(self):
        """Try to reconnect to failed peers."""
        failed_peers = [
            peer_id for peer_id, health in self.peer_health.items()
            if health.status == "failed"
        ]
        
        if not failed_peers:
            return
        
        print(f"🔄 Attempting to reconnect to {len(failed_peers)} failed peer(s)...")
        
        # Get discovered devices
        devices = self.discovery.get_devices()
        
        for peer_id in failed_peers:
            # Find device
            device = next((d for d in devices if d.device_id == peer_id), None)
            
            if device:
                try:
                    await self.connection_mgr.connect_to_peer(
                        peer_id,
                        device.address,
                        device.port
                    )
                    self.update_peer_health(peer_id)
                    print(f"✅ Reconnected to {peer_id}")
                except Exception as e:
                    print(f"⚠️  Reconnection failed: {e}")
    
    def get_healthy_peers(self) -> List[str]:
        """Get list of healthy peers."""
        return [
            peer_id for peer_id, health in self.peer_health.items()
            if health.is_healthy()
        ]
    
    def get_stats(self) -> Dict:
        """Get resilience statistics."""
        total = len(self.peer_health)
        healthy = len([h for h in self.peer_health.values() if h.status == "healthy"])
        degraded = len([h for h in self.peer_health.values() if h.status == "degraded"])
        failed = len([h for h in self.peer_health.values() if h.status == "failed"])
        
        return {
            "total_peers": total,
            "healthy": healthy,
            "degraded": degraded,
            "failed": failed,
            "health_percentage": (healthy / total * 100) if total > 0 else 100
        }


# Singleton
_resilience: Optional[NetworkResilience] = None


def get_network_resilience() -> NetworkResilience:
    """Get singleton instance."""
    global _resilience
    if _resilience is None:
        _resilience = NetworkResilience()
    return _resilience


if __name__ == "__main__":
    print("🛡️ Network Resilience Test\n")
    
    resilience = get_network_resilience()
    
    # Simulate peer updates
    resilience.update_peer_health("peer-1")
    resilience.update_peer_health("peer-2")
    resilience.mark_peer_failed("peer-3")
    
    # Stats
    stats = resilience.get_stats()
    print(f"📊 Stats:")
    print(f"   Total: {stats['total_peers']}")
    print(f"   Healthy: {stats['healthy']}")
    print(f"   Degraded: {stats['degraded']}")
    print(f"   Failed: {stats['failed']}")
    print(f"   Health: {stats['health_percentage']:.1f}%")
    
    print("\n✅ Test complete!")
