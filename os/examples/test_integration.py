#!/usr/bin/env python3
"""
Integration Test for KI-ana OS

Tests all major components:
- Memory System
- Error Handling
- Brain Integration
- Voice (if available)
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from core.memory.memory_manager import get_memory_manager
from core.ai_engine.enhanced_brain import EnhancedAIBrain
from core.error_handler import ErrorHandler, KIanaError, ErrorCategory


async def test_memory_system():
    """Test memory system"""
    logger.info("\n🧠 Testing Memory System...")
    
    try:
        memory = await get_memory_manager()
        
        # Store a conversation
        conv_id = await memory.store_conversation(
            user_input="Test command",
            ai_response="Test response",
            context={"test": True}
        )
        logger.success(f"✅ Stored conversation: {conv_id}")
        
        # Get recent conversations
        recent = await memory.get_recent_conversations(limit=5)
        logger.success(f"✅ Retrieved {len(recent)} conversations")
        
        # Set preference
        await memory.set_preference("test_pref", "test_value")
        value = await memory.get_preference("test_pref")
        assert value == "test_value"
        logger.success(f"✅ Preferences working: {value}")
        
        # Learn pattern
        await memory.learn_pattern("test", {"pattern": "test"})
        patterns = await memory.get_patterns("test")
        logger.success(f"✅ Patterns working: {len(patterns)} patterns")
        
        # Get stats
        stats = memory.get_stats()
        logger.info(f"📊 Memory stats: {stats}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Memory test failed: {e}")
        return False


async def test_error_handling():
    """Test error handling"""
    logger.info("\n🚨 Testing Error Handling...")
    
    try:
        # Test error categorization
        error1 = Exception("connection timeout")
        result1 = ErrorHandler.handle_error(error1, context="test")
        assert result1["error_category"] == ErrorCategory.NETWORK
        logger.success(f"✅ Network error detected: {result1['error']}")
        
        # Test permission error
        error2 = PermissionError("Access denied")
        result2 = ErrorHandler.handle_error(error2, context="test")
        assert result2["error_category"] == ErrorCategory.PERMISSION
        logger.success(f"✅ Permission error detected: {result2['error']}")
        
        # Test custom error
        error3 = KIanaError(
            "Custom error",
            category=ErrorCategory.CONFIGURATION,
            recovery_suggestions=["Try this", "Or this"]
        )
        result3 = ErrorHandler.handle_error(error3, context="test")
        assert len(result3["recovery_suggestions"]) == 2
        logger.success(f"✅ Custom error working: {len(result3['recovery_suggestions'])} suggestions")
        
        return True
    except Exception as e:
        logger.error(f"❌ Error handling test failed: {e}")
        return False


async def test_brain_integration():
    """Test AI Brain with memory integration"""
    logger.info("\n🧠 Testing Brain Integration...")
    
    try:
        brain = EnhancedAIBrain()
        await brain.initialize()
        
        # Check memory is initialized
        assert brain.memory_manager is not None
        logger.success("✅ Memory manager initialized in brain")
        
        # Process a command
        result = await brain.process_command("Zeige System Info")
        logger.info(f"Command result: success={result.get('success')}, response={result.get('response')[:100]}")
        
        # Check conversation was stored
        recent = await brain.memory_manager.get_recent_conversations(limit=1)
        if recent and "Zeige System Info" in recent[0]["user_input"]:
            logger.success("✅ Conversation stored in memory")
        else:
            logger.warning("⚠️ Conversation not found in memory")
        
        return True
    except Exception as e:
        logger.error(f"❌ Brain integration test failed: {e}")
        return False


async def test_voice_availability():
    """Test if voice components are available"""
    logger.info("\n🎤 Testing Voice Availability...")
    
    try:
        from core.voice.speech_to_text import get_stt
        from core.voice.text_to_speech import get_tts
        
        stt = await get_stt()
        tts = await get_tts()
        
        if stt.is_available:
            logger.success("✅ STT available")
        else:
            logger.warning("⚠️ STT not available - install dependencies")
        
        if tts.is_available:
            logger.success("✅ TTS available")
        else:
            logger.warning("⚠️ TTS not available - install dependencies")
        
        return True
    except Exception as e:
        logger.error(f"❌ Voice test failed: {e}")
        return False


async def main():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("🧪 KI-ana OS Integration Tests")
    logger.info("=" * 60)
    
    results = {}
    
    # Run tests
    results["memory"] = await test_memory_system()
    results["error_handling"] = await test_error_handling()
    results["brain_integration"] = await test_brain_integration()
    results["voice"] = await test_voice_availability()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
    
    total_passed = sum(1 for p in results.values() if p)
    total_tests = len(results)
    
    logger.info(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        logger.success("\n🎉 ALL TESTS PASSED!")
    else:
        logger.warning(f"\n⚠️ {total_tests - total_passed} test(s) failed")
    
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
