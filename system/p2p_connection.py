"""
P2P Connection Manager using WebRTC

Establishes direct peer-to-peer connections between devices.
No central server needed (except for initial signaling)!

Features:
- WebRTC Data Channels
- NAT Traversal (STUN)
- Automatic connection management
- Message passing
- Connection state tracking
"""
from __future__ import annotations
import asyncio
import json
import uuid
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, asdict
from pathlib import Path
import sys

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

try:
    from aiortc import RTCPeerConnection, RTCDataChannel, RTCSessionDescription, RTCIceCandidate
    from aiortc.contrib.signaling import TcpSocketSignaling, object_from_string, object_to_string
    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False
    print("⚠️  aiortc not available. Install with: pip install aiortc")


@dataclass
class P2PMessage:
    """Message sent over P2P connection."""
    type: str
    data: Any
    sender_id: str
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'P2PMessage':
        data = json.loads(json_str)
        return cls(**data)


class P2PConnection:
    """
    Represents a P2P connection to another device.
    """
    
    def __init__(self, peer_id: str, device_id: str):
        self.peer_id = peer_id
        self.device_id = device_id
        self.pc: Optional[RTCPeerConnection] = None
        self.channel: Optional[RTCDataChannel] = None
        self.connected = False
        self.on_message: Optional[Callable[[P2PMessage], None]] = None
        self.on_state_change: Optional[Callable[[str], None]] = None
    
    async def create_offer(self) -> Dict[str, Any]:
        """Create WebRTC offer."""
        if not AIORTC_AVAILABLE:
            raise RuntimeError("aiortc not available")
        
        # Create peer connection
        self.pc = RTCPeerConnection()
        
        # Create data channel
        self.channel = self.pc.createDataChannel("kiana-p2p")
        self._setup_channel()
        
        # Create offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        
        return {
            "sdp": self.pc.localDescription.sdp,
            "type": self.pc.localDescription.type
        }
    
    async def create_answer(self, offer: Dict[str, Any]) -> Dict[str, Any]:
        """Create WebRTC answer."""
        if not AIORTC_AVAILABLE:
            raise RuntimeError("aiortc not available")
        
        # Create peer connection
        self.pc = RTCPeerConnection()
        
        # Set remote description
        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=offer["sdp"], type=offer["type"])
        )
        
        # Setup channel handler
        @self.pc.on("datachannel")
        def on_datachannel(channel):
            self.channel = channel
            self._setup_channel()
        
        # Create answer
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        
        return {
            "sdp": self.pc.localDescription.sdp,
            "type": self.pc.localDescription.type
        }
    
    async def set_answer(self, answer: Dict[str, Any]):
        """Set remote answer."""
        if not self.pc:
            raise RuntimeError("No peer connection")
        
        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
        )
    
    def _setup_channel(self):
        """Setup data channel handlers."""
        if not self.channel:
            return
        
        @self.channel.on("open")
        def on_open():
            self.connected = True
            print(f"✅ P2P connection established with {self.peer_id}")
            if self.on_state_change:
                self.on_state_change("connected")
        
        @self.channel.on("close")
        def on_close():
            self.connected = False
            print(f"👋 P2P connection closed with {self.peer_id}")
            if self.on_state_change:
                self.on_state_change("disconnected")
        
        @self.channel.on("message")
        def on_message(message):
            try:
                msg = P2PMessage.from_json(message)
                if self.on_message:
                    self.on_message(msg)
            except Exception as e:
                print(f"⚠️  Error parsing message: {e}")
    
    def send(self, message: P2PMessage):
        """Send message over P2P connection."""
        if not self.connected or not self.channel:
            raise RuntimeError("Not connected")
        
        self.channel.send(message.to_json())
    
    async def close(self):
        """Close connection."""
        if self.channel:
            self.channel.close()
        if self.pc:
            await self.pc.close()
        self.connected = False


class P2PConnectionManager:
    """
    Manages P2P connections to multiple peers.
    
    Singleton pattern.
    """
    
    _instance: Optional['P2PConnectionManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        if not AIORTC_AVAILABLE:
            print("❌ aiortc not available")
            self._initialized = True
            return
        
        self._initialized = True
        
        # Device ID
        from submind_manager import get_submind_manager
        self.device_id = get_submind_manager().this_device_id
        
        # Active connections
        self.connections: Dict[str, P2PConnection] = {}
        
        # Message handlers
        self.message_handlers: Dict[str, Callable[[P2PMessage], None]] = {}
        
        print(f"✅ P2P Connection Manager initialized")
    
    async def connect_to_peer(self, peer_id: str, peer_address: str, peer_port: int) -> bool:
        """
        Connect to a peer.
        
        Args:
            peer_id: Peer's device ID
            peer_address: Peer's IP address
            peer_port: Peer's port
        
        Returns:
            True if successful
        """
        if not AIORTC_AVAILABLE:
            return False
        
        if peer_id in self.connections:
            print(f"⚠️  Already connected to {peer_id}")
            return True
        
        print(f"🔗 Connecting to {peer_id} @ {peer_address}:{peer_port}...")
        
        # Create connection
        connection = P2PConnection(peer_id, self.device_id)
        connection.on_message = self._on_message
        connection.on_state_change = lambda state: self._on_state_change(peer_id, state)
        
        try:
            # Create offer
            offer = await connection.create_offer()
            
            # Send offer to peer (simplified - in reality use signaling server)
            # For now, we'll use a simple HTTP-based signaling
            answer = await self._signal_offer(peer_address, peer_port, offer)
            
            # Set answer
            await connection.set_answer(answer)
            
            # Store connection
            self.connections[peer_id] = connection
            
            print(f"✅ Connected to {peer_id}")
            return True
        
        except Exception as e:
            print(f"❌ Failed to connect to {peer_id}: {e}")
            return False
    
    async def _signal_offer(self, address: str, port: int, offer: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send offer to peer via signaling.
        
        In a real implementation, this would use a signaling server.
        For simplicity, we'll use direct HTTP.
        """
        import aiohttp
        
        url = f"http://{address}:{port}/api/p2p/signal"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"type": "offer", "data": offer}) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["data"]
                else:
                    raise RuntimeError(f"Signaling failed: {resp.status}")
    
    def _on_message(self, message: P2PMessage):
        """Handle incoming message."""
        # Call registered handler
        handler = self.message_handlers.get(message.type)
        if handler:
            handler(message)
        else:
            print(f"⚠️  No handler for message type: {message.type}")
    
    def _on_state_change(self, peer_id: str, state: str):
        """Handle connection state change."""
        print(f"🔄 Connection to {peer_id}: {state}")
        
        if state == "disconnected":
            # Remove connection
            if peer_id in self.connections:
                del self.connections[peer_id]
    
    def register_handler(self, message_type: str, handler: Callable[[P2PMessage], None]):
        """Register a message handler."""
        self.message_handlers[message_type] = handler
        print(f"✅ Registered handler for: {message_type}")
    
    def send_to_peer(self, peer_id: str, message_type: str, data: Any):
        """Send message to a peer."""
        connection = self.connections.get(peer_id)
        if not connection:
            raise RuntimeError(f"Not connected to {peer_id}")
        
        import time
        message = P2PMessage(
            type=message_type,
            data=data,
            sender_id=self.device_id,
            timestamp=time.time()
        )
        
        connection.send(message)
    
    def broadcast(self, message_type: str, data: Any):
        """Broadcast message to all connected peers."""
        import time
        message = P2PMessage(
            type=message_type,
            data=data,
            sender_id=self.device_id,
            timestamp=time.time()
        )
        
        for connection in self.connections.values():
            if connection.connected:
                connection.send(message)
    
    def get_connected_peers(self) -> List[str]:
        """Get list of connected peer IDs."""
        return [
            peer_id for peer_id, conn in self.connections.items()
            if conn.connected
        ]
    
    async def disconnect_from_peer(self, peer_id: str):
        """Disconnect from a peer."""
        connection = self.connections.get(peer_id)
        if connection:
            await connection.close()
            del self.connections[peer_id]
            print(f"✅ Disconnected from {peer_id}")
    
    async def disconnect_all(self):
        """Disconnect from all peers."""
        for peer_id in list(self.connections.keys()):
            await self.disconnect_from_peer(peer_id)


# Singleton instance
_manager: Optional[P2PConnectionManager] = None


def get_connection_manager() -> P2PConnectionManager:
    """Get the singleton connection manager instance."""
    global _manager
    if _manager is None:
        _manager = P2PConnectionManager()
    return _manager


if __name__ == "__main__":
    # Quick test
    print("🔗 P2P Connection Manager Test\n")
    
    if not AIORTC_AVAILABLE:
        print("❌ aiortc not installed. Install with:")
        print("   pip install aiortc")
        exit(1)
    
    async def test():
        manager = get_connection_manager()
        
        # Register message handler
        def on_hello(message: P2PMessage):
            print(f"📨 Received hello from {message.sender_id}: {message.data}")
        
        manager.register_handler("hello", on_hello)
        
        print("✅ P2P Connection Manager ready")
        print("   Device ID:", manager.device_id)
        print("\n💡 To test P2P connections:")
        print("   1. Start discovery service")
        print("   2. Discover peers")
        print("   3. Connect using: await manager.connect_to_peer(peer_id, address, port)")
        print("   4. Send messages using: manager.send_to_peer(peer_id, 'hello', 'Hi!')")
    
    asyncio.run(test())
    
    print("\n✅ Test complete!")
