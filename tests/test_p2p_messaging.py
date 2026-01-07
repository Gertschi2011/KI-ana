"""
Tests für P2P Messaging System

Unit Tests + E2E Tests
"""
import sys
from pathlib import Path
import time

# Add system path (repo-local, CI-safe)
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "system"))

from p2p_messaging import get_p2p_messaging, MessageQueue, PlainMessage


def test_message_queue():
    """Test message queue persistence."""
    print("\n📦 Testing Message Queue...")
    
    import tempfile
    import shutil
    
    # Create temp queue
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        queue = MessageQueue(temp_dir)
        
        # Create test message
        from p2p_messaging import EncryptedMessage, MessageStatus
        msg = EncryptedMessage(
            message_id="test-123",
            sender_id="device-a",
            recipient_id="device-b",
            encrypted_content="encrypted",
            nonce="nonce",
            timestamp=time.time(),
            status=MessageStatus.PENDING.value
        )
        
        # Add to queue
        queue.add(msg)
        assert len(queue.pending) == 1
        print("✅ Message added to queue")
        
        # Check persistence
        queue2 = MessageQueue(temp_dir)
        assert len(queue2.pending) == 1
        print("✅ Queue persisted to disk")
        
        # Mark delivered
        queue2.mark_delivered("test-123")
        assert len(queue2.pending) == 0
        assert len(queue2.delivered) == 1
        print("✅ Message marked as delivered")
        
        # Check idempotency
        assert queue2.is_duplicate("test-123")
        print("✅ Duplicate detection works")
        
    finally:
        shutil.rmtree(temp_dir)
    
    return True


def test_encryption():
    """Test E2E encryption."""
    print("\n🔒 Testing E2E Encryption...")
    
    try:
        from nacl.public import PrivateKey, Box
        
        # Generate keys for two devices
        alice_private = PrivateKey.generate()
        alice_public = alice_private.public_key
        
        bob_private = PrivateKey.generate()
        bob_public = bob_private.public_key
        
        # Alice encrypts message for Bob
        alice_box = Box(alice_private, bob_public)
        
        plain_msg = PlainMessage(text="Hello Bob!", metadata={"from": "Alice"})
        encrypted = alice_box.encrypt(plain_msg.to_json().encode())
        
        print("✅ Message encrypted")
        
        # Bob decrypts message from Alice
        bob_box = Box(bob_private, alice_public)
        decrypted = bob_box.decrypt(encrypted)
        
        decrypted_msg = PlainMessage.from_json(decrypted.decode())
        
        assert decrypted_msg.text == "Hello Bob!"
        assert decrypted_msg.metadata["from"] == "Alice"
        
        print("✅ Message decrypted correctly")
        print(f"   Text: {decrypted_msg.text}")
        
    except Exception as e:
        print(f"❌ Encryption test failed: {e}")
        return False
    
    return True


def test_messaging_service():
    """Test messaging service initialization."""
    print("\n💬 Testing Messaging Service...")
    
    try:
        messaging = get_p2p_messaging()
        
        # Check keys
        assert messaging.private_key is not None
        assert messaging.public_key is not None
        print("✅ Encryption keys initialized")
        
        # Check public key format
        pub_key = messaging.get_public_key()
        assert len(pub_key) > 0
        print(f"✅ Public key: {pub_key[:32]}...")
        
        # Check stats
        stats = messaging.get_stats()
        assert "pending_messages" in stats
        assert "delivered_messages" in stats
        print(f"✅ Stats: {stats}")
        
    except Exception as e:
        print(f"❌ Service test failed: {e}")
        return False
    
    return True


def run_all_tests():
    """Run all messaging tests."""
    print("="*60)
    print("🧪 P2P Messaging Tests")
    print("="*60)
    
    tests = [
        ("Message Queue", test_message_queue),
        ("E2E Encryption", test_encryption),
        ("Messaging Service", test_messaging_service),
    ]
    
    results = {}
    
    for name, test_func in tests:
        try:
            success = test_func()
            results[name] = "✅ PASS" if success else "❌ FAIL"
        except Exception as e:
            results[name] = f"❌ ERROR: {e}"
            print(f"❌ Test failed: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)
    
    for name, result in results.items():
        print(f"{name:30} {result}")
    
    passed = sum(1 for r in results.values() if "✅" in r)
    total = len(results)
    
    print(f"\n{'='*60}")
    print(f"Result: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print(f"{'='*60}")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
