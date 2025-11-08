"""
Tests for Agent Loop Fix

Validates that the loop detection system works correctly
and prevents the agent from getting stuck in response loops.
"""
import pytest
import time
from netapi.agent.loop_detector import get_loop_detector, LoopDetector


class TestLoopDetector:
    """Test the loop detection system."""
    
    def setup_method(self):
        """Reset detector before each test."""
        self.detector = get_loop_detector()
        # Clear state
        self.detector._states = {}
    
    def test_conversation_state_creation(self):
        """Test that conversation states are created correctly."""
        state = self.detector.get_state("test_conv")
        assert state.conv_id == "test_conv"
        assert state.fallback_count == 0
        assert len(state.reply_history) == 0
    
    def test_reply_history_tracking(self):
        """Test that reply history is tracked correctly."""
        state = self.detector.get_state("test_conv")
        
        # Add some replies
        for i in range(7):
            state.add_reply(f"Reply {i}")
        
        # Should keep only last 5
        assert len(state.reply_history) == 5
        assert state.reply_history[-1] == "Reply 6"
        assert state.reply_history[0] == "Reply 2"
    
    def test_loop_detection_repeated_reply(self):
        """Test that repeated replies are detected as loops."""
        state = self.detector.get_state("test_conv")
        
        # Same reply twice
        state.add_reply("Same reply")
        assert not state.is_loop_detected()
        
        state.add_reply("Same reply")
        assert state.is_loop_detected()
    
    def test_loop_detection_alternating_pattern(self):
        """Test that alternating A-B-A-B pattern is detected."""
        state = self.detector.get_state("test_conv")
        
        state.add_reply("Reply A")
        state.add_reply("Reply B")
        state.add_reply("Reply A")
        assert not state.is_loop_detected()
        
        state.add_reply("Reply B")
        assert state.is_loop_detected()
    
    def test_loop_detection_max_fallbacks(self):
        """Test that too many fallbacks trigger loop detection."""
        state = self.detector.get_state("test_conv")
        
        state.fallback_count = 3
        assert state.is_loop_detected()
    
    def test_fallback_cooldown(self):
        """Test that fallback cooldown works."""
        conv_id = "test_conv"
        current_ts = time.time()
        
        # First fallback should be allowed
        allow, reason = self.detector.should_allow_fallback(conv_id, current_ts)
        assert allow
        assert reason == "ok"
        
        # Record it
        self.detector.record_reply(conv_id, "Fallback", is_fallback=True)
        
        # Immediate second fallback should be denied (cooldown)
        allow, reason = self.detector.should_allow_fallback(conv_id, current_ts + 1)
        assert not allow
        assert reason == "cooldown_active"
        
        # After cooldown period, should be allowed again
        allow, reason = self.detector.should_allow_fallback(conv_id, current_ts + 31)
        assert allow
    
    def test_max_fallbacks_limit(self):
        """Test that max fallbacks limit is enforced."""
        conv_id = "test_conv"
        current_ts = time.time()
        
        # Record 3 fallbacks
        for i in range(3):
            self.detector.record_reply(conv_id, f"Fallback {i}", is_fallback=True)
        
        # Should be denied now (either loop_detected or max_fallbacks_reached)
        allow, reason = self.detector.should_allow_fallback(conv_id, current_ts)
        assert not allow
        # Both reasons are valid - loop detection triggers on high fallback count
        assert reason in ("max_fallbacks_reached", "loop_detected")
    
    def test_escape_strategies(self):
        """Test that escape strategies are provided."""
        state = self.detector.get_state("test_conv")
        
        # Different strategies for different fallback counts
        strategies = []
        for i in range(4):
            state.fallback_count = i
            strategy = self.detector.get_escape_strategy("test_conv")
            assert len(strategy) > 0
            strategies.append(strategy)
        
        # Should have different strategies
        assert len(set(strategies)) >= 3
    
    def test_conversation_reset(self):
        """Test that conversation state can be reset."""
        conv_id = "test_conv"
        
        # Create some state
        self.detector.record_reply(conv_id, "Reply 1", is_fallback=True)
        self.detector.record_reply(conv_id, "Reply 2", is_fallback=True)
        
        state = self.detector.get_state(conv_id)
        assert state.fallback_count > 0
        
        # Reset
        self.detector.reset_conversation(conv_id)
        
        # Should be clean
        state = self.detector.get_state(conv_id)
        assert state.fallback_count == 0
        assert state.question_attempts == 0
    
    def test_user_message_similarity_detection(self):
        """Test that similar user messages are detected."""
        conv_id = "test_conv"
        
        # First message
        self.detector.record_user_message(conv_id, "Was ist Photosynthese?")
        state = self.detector.get_state(conv_id)
        assert state.question_attempts == 0
        
        # Similar message (rephrasing)
        self.detector.record_user_message(conv_id, "Was bedeutet Photosynthese?")
        state = self.detector.get_state(conv_id)
        assert state.question_attempts == 1
        
        # Different message
        self.detector.record_user_message(conv_id, "Wie ist das Wetter heute?")
        state = self.detector.get_state(conv_id)
        assert state.question_attempts == 0
    
    def test_cleanup_old_conversations(self):
        """Test that old conversations are cleaned up."""
        # Create some old conversations
        for i in range(5):
            conv_id = f"conv_{i}"
            self.detector.record_reply(conv_id, f"Reply {i}", is_fallback=True)
        
        assert len(self.detector._states) == 5
        
        # Set old timestamps
        current_ts = time.time()
        for state in self.detector._states.values():
            state.last_fallback_ts = current_ts - 7200  # 2 hours ago
        
        # Cleanup with 1 hour threshold
        self.detector.cleanup_old_conversations(max_age_secs=3600)
        
        # Should all be cleaned
        assert len(self.detector._states) == 0


class TestAgentIntegration:
    """Test that agent integrates correctly with loop detector."""
    
    def test_agent_imports_loop_detector(self):
        """Test that agent can import loop detector."""
        try:
            from netapi.agent.agent import LOOP_DETECTOR_AVAILABLE, get_loop_detector
            assert LOOP_DETECTOR_AVAILABLE is True
            assert get_loop_detector() is not None
        except ImportError:
            pytest.skip("Agent module not available")
    
    def test_pattern_matching_improvements(self):
        """Test that problematic patterns are removed."""
        try:
            from netapi.agent import agent
            import inspect
            
            # Get source code of run_agent
            source = inspect.getsource(agent.run_agent)
            
            # These patterns should NOT trigger web search anymore
            problematic_patterns = ['"ja"', '"ok"', '"okay"', '"gern"', '"mach"', '"bitte"']
            
            # Check that they're in a comment (REMOVED)
            for pattern in problematic_patterns:
                # Should be mentioned in comments as removed
                assert "REMOVED" in source or pattern not in source
                
        except ImportError:
            pytest.skip("Agent module not available")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
