"""
Unit tests for Learning Hub
"""

import pytest
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from netapi.learning.hub import (
    LearningHub,
    Interaction,
    ToolStatistics
)


class TestLearningHub:
    """Test suite for LearningHub"""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def hub(self, temp_storage):
        """Create LearningHub instance with temp storage"""
        return LearningHub(storage_path=temp_storage)
    
    def test_hub_initialization(self, hub):
        """Test that hub initializes correctly"""
        assert len(hub.interactions) == 0
        assert len(hub.tool_stats) == 0
        assert hub.storage_path.exists()
    
    def test_record_interaction(self, hub):
        """Test recording interactions"""
        interaction_id = hub.record_interaction(
            question="Was ist Python?",
            answer="Eine Programmiersprache",
            quality_score=0.85,
            tools_used=["memory"],
            retry_count=0
        )
        
        assert len(hub.interactions) == 1
        assert interaction_id is not None
        
        interaction = hub.interactions[0]
        assert interaction.question == "Was ist Python?"
        assert interaction.quality_score == 0.85
    
    def test_add_feedback(self, hub):
        """Test adding user feedback"""
        # Record interaction
        interaction_id = hub.record_interaction(
            question="Test",
            answer="Test answer",
            quality_score=0.7,
            tools_used=[],
            retry_count=0
        )
        
        # Add positive feedback
        hub.add_feedback(interaction_id, "positive")
        
        interaction = hub.interactions[0]
        assert interaction.user_feedback == "positive"
    
    def test_add_correction(self, hub):
        """Test adding user correction"""
        interaction_id = hub.record_interaction(
            question="Was ist 2+2?",
            answer="5",  # Wrong!
            quality_score=0.3,
            tools_used=["calc"],
            retry_count=0
        )
        
        # Add correction
        hub.add_feedback(interaction_id, "negative", correction="4")
        
        interaction = hub.interactions[0]
        assert interaction.user_correction == "4"
        
        # Check that correction was logged
        corrections_file = hub.storage_path / "corrections.jsonl"
        assert corrections_file.exists()
    
    def test_tool_success_tracking(self, hub):
        """Test tracking tool success rates"""
        # Record successful use
        hub.record_tool_use("calc", success=True, response_time_ms=50)
        
        assert "calc" in hub.tool_stats
        stats = hub.tool_stats["calc"]
        assert stats.total_uses == 1
        assert stats.successes == 1
        assert stats.success_rate() == 1.0
        
        # Record failure
        hub.record_tool_use("calc", success=False, response_time_ms=100)
        
        assert stats.total_uses == 2
        assert stats.successes == 1
        assert stats.failures == 1
        assert stats.success_rate() == 0.5
    
    def test_tool_recommendations(self, hub):
        """Test tool recommendation based on learning"""
        # Simulate learning
        hub.record_interaction(
            question="Was ist Python?",
            answer="Programming language",
            quality_score=0.9,
            tools_used=["memory", "web"],
            retry_count=0
        )
        
        # Record tool successes
        hub.record_tool_use("memory", True, 100)
        hub.record_tool_use("memory", True, 150)
        hub.record_tool_use("web", True, 200)
        hub.record_tool_use("calc", False, 50)
        
        # Get recommendations
        recommendations = hub.recommend_tools_for_question("Was ist JavaScript?")
        
        assert len(recommendations) > 0
        # Memory should be recommended (high success rate)
        tool_names = [t[0] for t in recommendations]
        assert "memory" in tool_names
    
    def test_statistics(self, hub):
        """Test statistics generation"""
        # Add some data
        hub.record_interaction("Q1", "A1", 0.8, ["calc"], 0)
        hub.record_interaction("Q2", "A2", 0.9, ["memory"], 1)
        hub.record_interaction("Q3", "A3", 0.7, ["web"], 0)
        
        hub.record_tool_use("calc", True, 100)
        hub.record_tool_use("memory", True, 150)
        
        stats = hub.get_statistics()
        
        assert stats["total_interactions"] == 3
        assert 0.7 <= stats["avg_quality"] <= 0.9
        assert "calc" in stats["tools"]
        assert "memory" in stats["tools"]
    
    def test_persistence(self, temp_storage):
        """Test that data is persisted to disk"""
        # Create hub and add data
        hub1 = LearningHub(storage_path=temp_storage)
        hub1.record_interaction("Test", "Answer", 0.8, ["calc"], 0)
        hub1.record_tool_use("calc", True, 100)
        hub1._save_to_disk()
        
        # Create new hub with same storage
        hub2 = LearningHub(storage_path=temp_storage)
        
        # Should have loaded the data
        assert "calc" in hub2.tool_stats
        assert hub2.tool_stats["calc"].total_uses == 1


class TestToolStatistics:
    """Test ToolStatistics dataclass"""
    
    def test_success_rate_calculation(self):
        """Test success rate calculation"""
        stats = ToolStatistics(name="test_tool")
        
        # No data = 50% default
        assert stats.success_rate() == 0.5
        
        # Add successes and failures
        stats.total_uses = 10
        stats.successes = 7
        stats.failures = 3
        
        assert stats.success_rate() == 0.7
    
    def test_update_statistics(self):
        """Test updating statistics"""
        stats = ToolStatistics(name="test_tool")
        
        # Update with success
        stats.update(success=True, response_time_ms=100)
        
        assert stats.total_uses == 1
        assert stats.successes == 1
        assert stats.failures == 0
        
        # Update with failure
        stats.update(success=False, response_time_ms=200)
        
        assert stats.total_uses == 2
        assert stats.successes == 1
        assert stats.failures == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
