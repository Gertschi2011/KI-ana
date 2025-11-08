"""
P2P Device Discovery using mDNS/Zeroconf

Automatically discovers KI_ana devices in the local network.
No central server needed!

Features:
- Automatic device discovery
- Service registration
- Heartbeat mechanism
- Device metadata exchange
"""
from __future__ import annotations
import socket
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
import sys

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

try:
    from zeroconf import ServiceInfo, Zeroconf, ServiceBrowser, ServiceListener
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False
    print("⚠️  Zeroconf not available. Install with: pip install zeroconf")

from submind_manager import get_submind_manager


@dataclass
class DiscoveredDevice:
    """Represents a discovered device."""
    device_id: str
    name: str
    role: str
    device_type: str
    address: str
    port: int
    capabilities: List[str]
    trust_level: float
    last_seen: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_service_info(cls, info: ServiceInfo) -> 'DiscoveredDevice':
        """Create from Zeroconf ServiceInfo."""
        props = {k.decode(): v.decode() if isinstance(v, bytes) else v 
                for k, v in info.properties.items()}
        
        # Get first IPv4 address
        address = None
        for addr in info.parsed_addresses():
            if ':' not in addr:  # IPv4
                address = addr
                break
        
        return cls(
            device_id=props.get('device_id', ''),
            name=props.get('name', ''),
            role=props.get('role', 'submind'),
            device_type=props.get('device_type', 'unknown'),
            address=address or '',
            port=info.port,
            capabilities=props.get('capabilities', '').split(','),
            trust_level=float(props.get('trust_level', '0.6')),
            last_seen=int(time.time())
        )


class DeviceListener(ServiceListener):
    """Listens for device announcements."""
    
    def __init__(self, discovery_service: 'P2PDiscoveryService'):
        self.discovery = discovery_service
    
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a new service is discovered."""
        info = zc.get_service_info(type_, name)
        if info:
            try:
                device = DiscoveredDevice.from_service_info(info)
                self.discovery._on_device_discovered(device)
            except Exception as e:
                print(f"⚠️  Error parsing service info: {e}")
    
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a service goes offline."""
        # Extract device_id from name
        # Format: "device_id._kiana._tcp.local."
        device_id = name.split('.')[0]
        self.discovery._on_device_removed(device_id)
    
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is updated."""
        info = zc.get_service_info(type_, name)
        if info:
            try:
                device = DiscoveredDevice.from_service_info(info)
                self.discovery._on_device_updated(device)
            except Exception as e:
                print(f"⚠️  Error updating service info: {e}")


class P2PDiscoveryService:
    """
    P2P Device Discovery Service using mDNS/Zeroconf.
    
    Automatically discovers and announces KI_ana devices in the network.
    """
    
    _instance: Optional['P2PDiscoveryService'] = None
    
    SERVICE_TYPE = "_kiana._tcp.local."
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        if not ZEROCONF_AVAILABLE:
            print("❌ Zeroconf not available")
            self._initialized = True
            return
        
        self._initialized = True
        
        # Zeroconf instance
        self.zeroconf = Zeroconf()
        
        # Submind manager
        self.submind_manager = get_submind_manager()
        
        # Discovered devices
        self.devices: Dict[str, DiscoveredDevice] = {}
        
        # Service info
        self.service_info: Optional[ServiceInfo] = None
        
        # Callbacks
        self.on_device_discovered: Optional[Callable[[DiscoveredDevice], None]] = None
        self.on_device_removed: Optional[Callable[[str], None]] = None
        self.on_device_updated: Optional[Callable[[DiscoveredDevice], None]] = None
        
        # Browser
        self.browser: Optional[ServiceBrowser] = None
        
        print(f"✅ P2P Discovery Service initialized")
    
    def _get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            # Create a socket to get the local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def register_device(self, port: int = 8000) -> bool:
        """
        Register this device for discovery.
        
        Args:
            port: Port where the API is running
        
        Returns:
            True if successful
        """
        if not ZEROCONF_AVAILABLE:
            return False
        
        # Get this device info
        device = self.submind_manager.get_this_device()
        if not device:
            print("⚠️  No device registered in submind manager")
            return False
        
        # Get local IP
        local_ip = self._get_local_ip()
        
        # Create service info
        properties = {
            'device_id': device.id,
            'name': device.name,
            'role': device.role,
            'device_type': device.device_type,
            'capabilities': ','.join(device.capabilities),
            'trust_level': str(device.trust_level),
            'version': '3.0'
        }
        
        # Service name: device_id._kiana._tcp.local.
        service_name = f"{device.id}.{self.SERVICE_TYPE}"
        
        self.service_info = ServiceInfo(
            self.SERVICE_TYPE,
            service_name,
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            properties=properties,
            server=f"{device.name}.local."
        )
        
        # Register service
        try:
            self.zeroconf.register_service(self.service_info)
            print(f"✅ Device registered for discovery")
            print(f"   Name: {device.name}")
            print(f"   IP: {local_ip}:{port}")
            print(f"   Service: {service_name}")
            return True
        except Exception as e:
            print(f"❌ Failed to register service: {e}")
            return False
    
    def start_discovery(self) -> bool:
        """
        Start discovering other devices.
        
        Returns:
            True if successful
        """
        if not ZEROCONF_AVAILABLE:
            return False
        
        if self.browser:
            print("⚠️  Discovery already running")
            return True
        
        # Create listener
        listener = DeviceListener(self)
        
        # Start browser
        self.browser = ServiceBrowser(self.zeroconf, self.SERVICE_TYPE, listener)
        
        print(f"✅ Discovery started")
        print(f"   Listening for: {self.SERVICE_TYPE}")
        
        return True
    
    def stop_discovery(self):
        """Stop discovering devices."""
        if self.browser:
            self.browser.cancel()
            self.browser = None
            print("🛑 Discovery stopped")
    
    def unregister_device(self):
        """Unregister this device."""
        if self.service_info:
            try:
                self.zeroconf.unregister_service(self.service_info)
                print("✅ Device unregistered")
            except Exception as e:
                print(f"⚠️  Error unregistering: {e}")
            finally:
                self.service_info = None
    
    def shutdown(self):
        """Shutdown discovery service."""
        self.stop_discovery()
        self.unregister_device()
        self.zeroconf.close()
        print("✅ Discovery service shutdown")
    
    def _on_device_discovered(self, device: DiscoveredDevice):
        """Called when a new device is discovered."""
        # Don't add ourselves
        if device.device_id == self.submind_manager.this_device_id:
            return
        
        self.devices[device.device_id] = device
        
        print(f"🔍 Device discovered: {device.name}")
        print(f"   ID: {device.device_id}")
        print(f"   Address: {device.address}:{device.port}")
        print(f"   Role: {device.role}")
        
        # Update last seen in submind manager
        self.submind_manager.update_last_seen(device.device_id)
        
        # Call callback
        if self.on_device_discovered:
            self.on_device_discovered(device)
    
    def _on_device_removed(self, device_id: str):
        """Called when a device goes offline."""
        if device_id in self.devices:
            device = self.devices.pop(device_id)
            print(f"👋 Device offline: {device.name}")
            
            # Call callback
            if self.on_device_removed:
                self.on_device_removed(device_id)
    
    def _on_device_updated(self, device: DiscoveredDevice):
        """Called when a device is updated."""
        # Don't update ourselves
        if device.device_id == self.submind_manager.this_device_id:
            return
        
        self.devices[device.device_id] = device
        
        # Update last seen
        self.submind_manager.update_last_seen(device.device_id)
        
        # Call callback
        if self.on_device_updated:
            self.on_device_updated(device)
    
    def get_devices(self) -> List[DiscoveredDevice]:
        """Get all discovered devices."""
        return list(self.devices.values())
    
    def get_device(self, device_id: str) -> Optional[DiscoveredDevice]:
        """Get a specific device."""
        return self.devices.get(device_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get discovery statistics."""
        return {
            "total_devices": len(self.devices),
            "by_role": {
                role: len([d for d in self.devices.values() if d.role == role])
                for role in ["creator", "submind", "user", "sensor"]
            },
            "by_type": {
                dtype: len([d for d in self.devices.values() if d.device_type == dtype])
                for dtype in ["desktop", "mobile", "iot", "sensor"]
            }
        }


# Singleton instance
_service: Optional[P2PDiscoveryService] = None


def get_discovery_service() -> P2PDiscoveryService:
    """Get the singleton discovery service instance."""
    global _service
    if _service is None:
        _service = P2PDiscoveryService()
    return _service


if __name__ == "__main__":
    # Quick test
    print("🌐 P2P Discovery Service Test\n")
    
    if not ZEROCONF_AVAILABLE:
        print("❌ Zeroconf not installed. Install with:")
        print("   pip install zeroconf")
        exit(1)
    
    service = get_discovery_service()
    
    # Register this device
    print("📝 Registering this device...")
    success = service.register_device(port=8000)
    
    if not success:
        print("❌ Failed to register device")
        exit(1)
    
    # Start discovery
    print("\n🔍 Starting discovery...")
    service.start_discovery()
    
    # Wait and show discovered devices
    print("\n⏳ Waiting for devices (30 seconds)...")
    print("   (Start another instance on a different device to test)")
    
    for i in range(30):
        time.sleep(1)
        if i % 5 == 0 and i > 0:
            devices = service.get_devices()
            print(f"\n📊 Discovered {len(devices)} device(s):")
            for device in devices:
                print(f"  - {device.name} ({device.device_type}, {device.role})")
                print(f"    Address: {device.address}:{device.port}")
    
    # Final stats
    print("\n📊 Final Statistics:")
    stats = service.get_stats()
    print(f"  Total devices: {stats['total_devices']}")
    print(f"  By role: {stats['by_role']}")
    print(f"  By type: {stats['by_type']}")
    
    # Shutdown
    print("\n🛑 Shutting down...")
    service.shutdown()
    
    print("\n✅ Test complete!")
