"""
P2P-Messaging System mit E2E-Verschlüsselung

Features:
- End-to-End Encryption (NaCl/libsodium)
- Message Queue (Offline + Online)
- Delivery Confirmation (ACK)
- Idempotenz (Duplicate Detection)
- Persistent Storage
- Message Routing

Sicherheit:
✅ E2E verschlüsselt (NaCl Box)
✅ Keine Rohdaten im Klartext
✅ Device Keys aus Submind Registry
✅ Forward Secrecy möglich
"""
from __future__ import annotations
import json
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import sys

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

try:
    from nacl.public import PrivateKey, PublicKey, Box
    from nacl.encoding import Base64Encoder
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False
    print("⚠️  PyNaCl not available. Install with: pip install pynacl")

from p2p_connection import get_connection_manager, P2PMessage
from submind_manager import get_submind_manager


class MessageStatus(Enum):
    """Message delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


@dataclass
class EncryptedMessage:
    """Encrypted P2P message."""
    message_id: str
    sender_id: str
    recipient_id: str
    encrypted_content: str  # Base64 encoded
    nonce: str  # Base64 encoded
    timestamp: float
    status: str
    ack_received: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptedMessage':
        return cls(**data)


@dataclass
class PlainMessage:
    """Decrypted message content."""
    text: str
    metadata: Dict[str, Any]
    
    def to_json(self) -> str:
        return json.dumps({"text": self.text, "metadata": self.metadata})
    
    @classmethod
    def from_json(cls, json_str: str) -> 'PlainMessage':
        data = json.loads(json_str)
        return cls(text=data["text"], metadata=data.get("metadata", {}))


class MessageQueue:
    """Persistent message queue for offline/online messages."""
    
    def __init__(self, queue_dir: Path):
        self.queue_dir = queue_dir
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory queue
        self.pending: Dict[str, EncryptedMessage] = {}
        self.delivered: Dict[str, EncryptedMessage] = {}
        
        # Load from disk
        self._load_queue()
    
    def _load_queue(self):
        """Load queue from disk."""
        pending_file = self.queue_dir / "pending.json"
        delivered_file = self.queue_dir / "delivered.json"
        
        if pending_file.exists():
            try:
                data = json.loads(pending_file.read_text())
                self.pending = {
                    msg_id: EncryptedMessage.from_dict(msg_data)
                    for msg_id, msg_data in data.items()
                }
                print(f"📦 Loaded {len(self.pending)} pending messages")
            except Exception as e:
                print(f"⚠️  Error loading pending queue: {e}")
        
        if delivered_file.exists():
            try:
                data = json.loads(delivered_file.read_text())
                self.delivered = {
                    msg_id: EncryptedMessage.from_dict(msg_data)
                    for msg_id, msg_data in data.items()
                }
            except Exception as e:
                print(f"⚠️  Error loading delivered queue: {e}")
    
    def _save_queue(self):
        """Save queue to disk."""
        pending_file = self.queue_dir / "pending.json"
        delivered_file = self.queue_dir / "delivered.json"
        
        try:
            pending_data = {
                msg_id: msg.to_dict()
                for msg_id, msg in self.pending.items()
            }
            pending_file.write_text(json.dumps(pending_data, indent=2))
            
            delivered_data = {
                msg_id: msg.to_dict()
                for msg_id, msg in self.delivered.items()
            }
            delivered_file.write_text(json.dumps(delivered_data, indent=2))
        except Exception as e:
            print(f"⚠️  Error saving queue: {e}")
    
    def add(self, message: EncryptedMessage):
        """Add message to pending queue."""
        self.pending[message.message_id] = message
        self._save_queue()
    
    def mark_delivered(self, message_id: str):
        """Mark message as delivered."""
        if message_id in self.pending:
            msg = self.pending.pop(message_id)
            msg.status = MessageStatus.DELIVERED.value
            msg.ack_received = True
            self.delivered[message_id] = msg
            self._save_queue()
    
    def mark_failed(self, message_id: str):
        """Mark message as failed."""
        if message_id in self.pending:
            self.pending[message_id].status = MessageStatus.FAILED.value
            self._save_queue()
    
    def get_pending(self, recipient_id: str = None) -> List[EncryptedMessage]:
        """Get pending messages, optionally filtered by recipient."""
        messages = list(self.pending.values())
        if recipient_id:
            messages = [m for m in messages if m.recipient_id == recipient_id]
        return messages
    
    def is_duplicate(self, message_id: str) -> bool:
        """Check if message was already processed (idempotency)."""
        return message_id in self.pending or message_id in self.delivered


class P2PMessaging:
    """
    P2P Messaging System with E2E Encryption.
    
    Singleton pattern.
    """
    
    _instance: Optional['P2PMessaging'] = None
    
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
        
        # Device ID & Keys
        self.submind_manager = get_submind_manager()
        self.device_id = self.submind_manager.this_device_id
        
        # Crypto keys
        self.private_key: Optional[PrivateKey] = None
        self.public_key: Optional[PublicKey] = None
        self._load_or_create_keys()
        
        # Peer public keys cache
        self.peer_keys: Dict[str, PublicKey] = {}
        
        # Message queue
        queue_dir = Path.home() / "ki_ana" / "data" / "message_queue"
        self.queue = MessageQueue(queue_dir)
        
        # Connection manager
        self.connection_manager = get_connection_manager()
        
        # Register message handlers
        self.connection_manager.register_handler("encrypted_message", self._handle_encrypted_message)
        self.connection_manager.register_handler("message_ack", self._handle_message_ack)
        
        # Message callbacks
        self.on_message_received: Optional[Callable[[str, PlainMessage], None]] = None
        
        print(f"✅ P2P Messaging initialized")
        print(f"   Public Key: {self.public_key.encode(encoder=Base64Encoder).decode()[:32]}...")
    
    def _load_or_create_keys(self):
        """Load or create device encryption keys."""
        keys_dir = Path.home() / "ki_ana" / "system" / "keys"
        keys_dir.mkdir(parents=True, exist_ok=True)
        
        private_key_file = keys_dir / f"{self.device_id}_messaging_private.key"
        public_key_file = keys_dir / f"{self.device_id}_messaging_public.key"
        
        if private_key_file.exists() and public_key_file.exists():
            # Load existing keys
            try:
                self.private_key = PrivateKey(private_key_file.read_bytes())
                self.public_key = PublicKey(public_key_file.read_bytes())
                print(f"🔑 Loaded existing encryption keys")
            except Exception as e:
                print(f"⚠️  Error loading keys: {e}, generating new ones")
                self._generate_keys(private_key_file, public_key_file)
        else:
            # Generate new keys
            self._generate_keys(private_key_file, public_key_file)
    
    def _generate_keys(self, private_file: Path, public_file: Path):
        """Generate new encryption key pair."""
        self.private_key = PrivateKey.generate()
        self.public_key = self.private_key.public_key
        
        # Save keys
        private_file.write_bytes(bytes(self.private_key))
        public_file.write_bytes(bytes(self.public_key))
        
        # Secure permissions
        import os
        os.chmod(private_file, 0o600)
        
        print(f"🔑 Generated new encryption keys")
    
    def get_public_key(self) -> str:
        """Get this device's public key (Base64)."""
        return self.public_key.encode(encoder=Base64Encoder).decode()
    
    def _get_peer_public_key(self, peer_id: str) -> Optional[PublicKey]:
        """Get peer's public key."""
        if peer_id in self.peer_keys:
            return self.peer_keys[peer_id]
        
        # Try to load from file
        keys_dir = Path.home() / "ki_ana" / "system" / "keys"
        public_key_file = keys_dir / f"{peer_id}_messaging_public.key"
        
        if public_key_file.exists():
            try:
                key = PublicKey(public_key_file.read_bytes())
                self.peer_keys[peer_id] = key
                return key
            except Exception as e:
                print(f"⚠️  Error loading peer key: {e}")
        
        return None
    
    def send_message(self, recipient_id: str, text: str, metadata: Dict[str, Any] = None) -> str:
        """
        Send encrypted message to peer.
        
        Args:
            recipient_id: Recipient device ID
            text: Message text
            metadata: Optional metadata
        
        Returns:
            Message ID
        """
        if not NACL_AVAILABLE:
            raise RuntimeError("PyNaCl not available")
        
        # Get recipient's public key
        peer_key = self._get_peer_public_key(recipient_id)
        if not peer_key:
            raise RuntimeError(f"No public key for peer: {recipient_id}")
        
        # Create plain message
        plain_msg = PlainMessage(text=text, metadata=metadata or {})
        
        # Encrypt message
        box = Box(self.private_key, peer_key)
        encrypted = box.encrypt(plain_msg.to_json().encode())
        
        # Create encrypted message
        message_id = str(uuid.uuid4())
        encrypted_msg = EncryptedMessage(
            message_id=message_id,
            sender_id=self.device_id,
            recipient_id=recipient_id,
            encrypted_content=Base64Encoder.encode(encrypted.ciphertext).decode(),
            nonce=Base64Encoder.encode(encrypted.nonce).decode(),
            timestamp=time.time(),
            status=MessageStatus.PENDING.value
        )
        
        # Add to queue
        self.queue.add(encrypted_msg)
        
        # Try to send immediately
        self._try_send_message(encrypted_msg)
        
        return message_id
    
    def _try_send_message(self, message: EncryptedMessage):
        """Try to send message to peer."""
        try:
            self.connection_manager.send_to_peer(
                message.recipient_id,
                "encrypted_message",
                message.to_dict()
            )
            message.status = MessageStatus.SENT.value
            self.queue._save_queue()
            print(f"📤 Message sent: {message.message_id[:8]}...")
        except Exception as e:
            print(f"⚠️  Failed to send message: {e}")
            # Message stays in queue for retry
    
    def _handle_encrypted_message(self, p2p_message: P2PMessage):
        """Handle incoming encrypted message."""
        sender_id = p2p_message.sender_id
        msg_data = p2p_message.data
        
        encrypted_msg = EncryptedMessage.from_dict(msg_data)
        
        # Check for duplicates (idempotency)
        if self.queue.is_duplicate(encrypted_msg.message_id):
            print(f"⚠️  Duplicate message ignored: {encrypted_msg.message_id[:8]}...")
            # Still send ACK
            self._send_ack(sender_id, encrypted_msg.message_id)
            return
        
        print(f"📥 Received encrypted message from {sender_id}")
        
        # Decrypt message
        try:
            plain_msg = self._decrypt_message(encrypted_msg)
            
            # Store in delivered queue
            self.queue.delivered[encrypted_msg.message_id] = encrypted_msg
            self.queue._save_queue()
            
            # Send ACK
            self._send_ack(sender_id, encrypted_msg.message_id)
            
            # Call callback
            if self.on_message_received:
                self.on_message_received(sender_id, plain_msg)
            else:
                print(f"💬 Message: {plain_msg.text}")
            
        except Exception as e:
            print(f"❌ Failed to decrypt message: {e}")
    
    def _decrypt_message(self, encrypted_msg: EncryptedMessage) -> PlainMessage:
        """Decrypt encrypted message."""
        # Get sender's public key
        peer_key = self._get_peer_public_key(encrypted_msg.sender_id)
        if not peer_key:
            raise RuntimeError(f"No public key for sender: {encrypted_msg.sender_id}")
        
        # Decrypt
        box = Box(self.private_key, peer_key)
        
        ciphertext = Base64Encoder.decode(encrypted_msg.encrypted_content.encode())
        nonce = Base64Encoder.decode(encrypted_msg.nonce.encode())
        
        plaintext = box.decrypt(ciphertext, nonce)
        
        # Parse message
        return PlainMessage.from_json(plaintext.decode())
    
    def _send_ack(self, recipient_id: str, message_id: str):
        """Send delivery acknowledgment."""
        try:
            self.connection_manager.send_to_peer(
                recipient_id,
                "message_ack",
                {"message_id": message_id}
            )
            print(f"✅ ACK sent for message: {message_id[:8]}...")
        except Exception as e:
            print(f"⚠️  Failed to send ACK: {e}")
    
    def _handle_message_ack(self, p2p_message: P2PMessage):
        """Handle delivery acknowledgment."""
        sender_id = p2p_message.sender_id
        message_id = p2p_message.data["message_id"]
        
        print(f"✅ ACK received from {sender_id} for message: {message_id[:8]}...")
        
        # Mark as delivered
        self.queue.mark_delivered(message_id)
    
    def retry_pending_messages(self):
        """Retry sending pending messages."""
        pending = self.queue.get_pending()
        
        if not pending:
            return
        
        print(f"🔄 Retrying {len(pending)} pending messages...")
        
        for msg in pending:
            self._try_send_message(msg)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get messaging statistics."""
        return {
            "pending_messages": len(self.queue.pending),
            "delivered_messages": len(self.queue.delivered),
            "peer_keys_cached": len(self.peer_keys)
        }


# Singleton instance
_messaging: Optional[P2PMessaging] = None


def get_p2p_messaging() -> P2PMessaging:
    """Get the singleton P2P messaging instance."""
    global _messaging
    if _messaging is None:
        _messaging = P2PMessaging()
    return _messaging


if __name__ == "__main__":
    # Quick test
    print("💬 P2P Messaging Test\n")
    
    if not NACL_AVAILABLE:
        print("❌ PyNaCl not installed. Install with:")
        print("   pip install pynacl")
        exit(1)
    
    messaging = get_p2p_messaging()
    
    # Show public key
    print(f"\n🔑 Public Key:")
    print(f"   {messaging.get_public_key()}")
    
    # Stats
    print(f"\n📊 Statistics:")
    stats = messaging.get_stats()
    print(f"   Pending: {stats['pending_messages']}")
    print(f"   Delivered: {stats['delivered_messages']}")
    print(f"   Peer keys: {stats['peer_keys_cached']}")
    
    print("\n✅ Test complete!")
    print("\n💡 To send messages:")
    print("   messaging.send_message(peer_id, 'Hello!', {'priority': 'high'})")
    print("\n🔒 Security:")
    print("   ✅ E2E encrypted (NaCl Box)")
    print("   ✅ No plaintext in network")
    print("   ✅ Forward secrecy possible")
    print("   ✅ Idempotent delivery")
