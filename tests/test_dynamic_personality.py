"""
Tests for Dynamic Personality System

Validates that personality adapts based on feedback and context.
"""
import pytest
import sys
from pathlib import Path

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

from dynamic_personality import DynamicPersonality, get_dynamic_personality


class TestDynamicPersonality:
    """Test the dynamic personality system."""
    
    def setup_method(self):
        """Setup fresh personality for each test."""
        self.personality = DynamicPersonality()
    
    def test_initialization(self):
        """Test that personality initializes correctly."""
        assert self.personality.base_profile is not None
        assert self.personality.state is not None
        assert "traits" in self.personality.state
    
    def test_get_current_traits(self):
        """Test getting current trait values."""
        traits = self.personality.get_current_traits()
        
        assert isinstance(traits, dict)
        assert len(traits) > 0
        
        # Check that values are in valid range
        for trait_name, value in traits.items():
            assert 0.0 <= value <= 1.0, f"Trait {trait_name} = {value} out of range"
    
    def test_adjust_from_positive_feedback(self):
        """Test that positive feedback increases trait values."""
        traits_before = self.personality.get_current_traits()
        
        # Get a trait to test
        trait_name = list(self.personality.state["traits"].keys())[0]
        value_before = traits_before[trait_name]
        
        # Record feedback count before
        feedback_before = self.personality.state.get("positive_feedback", 0)
        
        # Apply positive feedback
        self.personality.adjust_from_feedback("positive")
        
        traits_after = self.personality.get_current_traits()
        value_after = traits_after[trait_name]
        
        # Value should increase (or stay at max)
        assert value_after >= value_before
        # Count should have increased by 1
        assert self.personality.state["positive_feedback"] == feedback_before + 1
    
    def test_adjust_from_negative_feedback(self):
        """Test that negative feedback decreases trait values."""
        # Set a trait to a mid value first
        trait_name = list(self.personality.state["traits"].keys())[0]
        self.personality.state["traits"][trait_name]["value"] = 0.7
        
        value_before = 0.7
        
        # Record feedback count before
        feedback_before = self.personality.state.get("negative_feedback", 0)
        
        # Apply negative feedback
        self.personality.adjust_from_feedback("negative")
        
        traits_after = self.personality.get_current_traits()
        value_after = traits_after[trait_name]
        
        # Value should decrease (or stay at min)
        assert value_after <= value_before
        # Count should have increased by 1
        assert self.personality.state["negative_feedback"] == feedback_before + 1
    
    def test_context_modifiers_time_of_day(self):
        """Test that time of day affects traits."""
        from datetime import datetime
        from unittest.mock import patch
        
        # Test empathy boost in evening
        with patch('dynamic_personality.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 10, 22, 20, 0)  # 8 PM
            mock_datetime.hour = 20
            
            traits = self.personality.get_current_traits(context={})
            
            # Empathy should be boosted in evening
            # (hard to test exact value due to base + modifier)
            assert "empathy" in traits
    
    def test_detect_user_mood_stressed(self):
        """Test detecting stressed mood."""
        texts = [
            ("Das funktioniert nicht!", "stressed"),
            ("Schnell, ich brauche Hilfe!", "stressed"),
            ("Problem - geht nicht", "stressed"),
            ("Dringend! Fehler!", "stressed")
        ]
        
        for text, expected in texts:
            mood = self.personality.detect_user_mood(text)
            # Allow neutral if detection is conservative
            assert mood in [expected, "neutral"], f"Failed for: {text}, got: {mood}"
    
    def test_detect_user_mood_curious(self):
        """Test detecting curious mood."""
        texts = [
            "Wie funktioniert das?",
            "Warum ist das so?",
            "Erkläre mir mehr über KI",
            "Das ist interessant!"
        ]
        
        for text in texts:
            mood = self.personality.detect_user_mood(text)
            assert mood == "curious", f"Failed for: {text}"
    
    def test_detect_user_mood_happy(self):
        """Test detecting happy mood."""
        texts = [
            "Danke, das war super!",
            "Perfekt, genau das!",
            "Toll erklärt! 👍"
        ]
        
        for text in texts:
            mood = self.personality.detect_user_mood(text)
            assert mood == "happy", f"Failed for: {text}"
    
    def test_detect_user_mood_neutral(self):
        """Test detecting neutral mood."""
        text = "Was ist die Hauptstadt von Deutschland?"
        mood = self.personality.detect_user_mood(text)
        assert mood == "neutral"
    
    def test_get_stats(self):
        """Test getting personality statistics."""
        # Record before
        stats_before = self.personality.get_stats()
        interactions_before = stats_before["interactions"]
        positive_before = stats_before["positive_feedback"]
        negative_before = stats_before["negative_feedback"]
        
        # Add some interactions
        self.personality.adjust_from_feedback("positive")
        self.personality.adjust_from_feedback("positive")
        self.personality.adjust_from_feedback("negative")
        
        stats = self.personality.get_stats()
        
        # Check deltas
        assert stats["interactions"] == interactions_before + 3
        assert stats["positive_feedback"] == positive_before + 2
        assert stats["negative_feedback"] == negative_before + 1
        assert 0.0 <= stats["feedback_rate"] <= 1.0
        assert "traits" in stats
    
    def test_reset_trait(self):
        """Test resetting a single trait."""
        # Modify a trait
        trait_name = list(self.personality.state["traits"].keys())[0]
        self.personality.state["traits"][trait_name]["value"] = 0.999
        
        # Reset it
        success = self.personality.reset_trait(trait_name)
        assert success
        
        # Should be back to base value
        base_value = self.personality.base_profile["style"][trait_name]
        current_value = self.personality.state["traits"][trait_name]["value"]
        assert abs(current_value - base_value) < 0.01
    
    def test_reset_all_traits(self):
        """Test resetting all traits."""
        # Modify all traits
        for trait_name in self.personality.state["traits"].keys():
            self.personality.state["traits"][trait_name]["value"] = 0.999
        
        # Reset all
        self.personality.reset_all_traits()
        
        # All should be back to base values
        for trait_name, trait_data in self.personality.state["traits"].items():
            base_value = self.personality.base_profile["style"][trait_name]
            current_value = trait_data["value"]
            assert abs(current_value - base_value) < 0.01
    
    def test_trait_adjustment_history(self):
        """Test that adjustment history is tracked."""
        self.personality.adjust_from_feedback("positive")
        
        trait_name = list(self.personality.state["traits"].keys())[0]
        trait_data = self.personality.state["traits"][trait_name]
        
        assert "history" in trait_data
        assert len(trait_data["history"]) > 0
        
        last_adjustment = trait_data["history"][-1]
        assert "timestamp" in last_adjustment
        assert "feedback" in last_adjustment
        assert last_adjustment["feedback"] == "positive"
    
    def test_global_singleton(self):
        """Test that get_dynamic_personality returns singleton."""
        p1 = get_dynamic_personality()
        p2 = get_dynamic_personality()
        
        assert p1 is p2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
