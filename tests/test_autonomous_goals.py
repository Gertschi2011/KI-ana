"""
Tests for Autonomous Learning Goals System

Validates that the AI can identify gaps and set its own learning goals.
"""
import pytest
import sys
from pathlib import Path

# Add system path (repo-local, CI-safe)
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "system"))

from autonomous_goals import (
    AutonomousGoalEngine,
    KnowledgeGap,
    LearningGoal,
    get_autonomous_goal_engine
)


class TestAutonomousGoalEngine:
    """Test the autonomous goal engine."""
    
    def setup_method(self):
        """Setup fresh engine for each test."""
        self.engine = AutonomousGoalEngine()
    
    def test_initialization(self):
        """Test that engine initializes correctly."""
        assert self.engine.base_dir is not None
        assert self.engine.runtime_dir is not None
        assert isinstance(self.engine.goals, list)
        assert isinstance(self.engine.gaps, list)
    
    def test_identify_knowledge_gaps(self):
        """Test that knowledge gaps are identified."""
        gaps = self.engine.identify_knowledge_gaps()
        
        assert isinstance(gaps, list)
        assert len(gaps) > 0
        
        # Check structure
        for gap in gaps:
            assert isinstance(gap, KnowledgeGap)
            assert gap.topic
            assert gap.gap_type in ["missing", "incomplete", "outdated", "high_demand"]
            assert 0.0 <= gap.priority_score <= 1.0
    
    def test_prioritize_goals(self):
        """Test that gaps are prioritized into goals."""
        # First identify gaps
        gaps = self.engine.identify_knowledge_gaps()
        
        # Prioritize
        goals = self.engine.prioritize_goals(gaps)
        
        assert isinstance(goals, list)
        assert len(goals) > 0
        
        # Check structure
        for goal in goals:
            assert isinstance(goal, LearningGoal)
            assert goal.topic
            assert goal.description
            assert goal.status == "pending"
            assert 0.0 <= goal.priority <= 1.0
            assert len(goal.keywords) > 0
            assert len(goal.sources) > 0
            assert len(goal.steps) > 0
    
    def test_goals_sorted_by_priority(self):
        """Test that goals are sorted by priority."""
        gaps = self.engine.identify_knowledge_gaps()
        goals = self.engine.prioritize_goals(gaps)
        
        # Check descending order
        priorities = [g.priority for g in goals]
        assert priorities == sorted(priorities, reverse=True)
    
    def test_get_top_goals(self):
        """Test getting top N goals."""
        gaps = self.engine.identify_knowledge_gaps()
        self.engine.prioritize_goals(gaps)
        
        top3 = self.engine.get_top_goals(3)
        
        assert len(top3) <= 3
        assert all(g.status == "pending" for g in top3)
        
        # Should be sorted by priority
        if len(top3) > 1:
            assert top3[0].priority >= top3[1].priority
    
    def test_aligns_with_core_identity(self):
        """Test core identity alignment check."""
        assert self.engine._aligns_with_core_identity("Artificial Intelligence")
        assert self.engine._aligns_with_core_identity("Machine Learning Basics")
        assert self.engine._aligns_with_core_identity("Technologie")
        
        assert not self.engine._aligns_with_core_identity("Random Topic")
    
    def test_is_researchable(self):
        """Test researchability check."""
        assert self.engine._is_researchable("Python Programming")
        assert self.engine._is_researchable("Climate Change")
        
        # Might be filtered as non-researchable
        # (though in practice most things can be researched)
        assert isinstance(self.engine._is_researchable("Magic Spells"), bool)
    
    def test_generate_keywords(self):
        """Test keyword generation."""
        keywords = self.engine._generate_keywords("Python")
        
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        assert "Python" in keywords[0]
    
    def test_suggest_sources(self):
        """Test source suggestion."""
        sources = self.engine._suggest_sources("Python Programming")
        
        assert isinstance(sources, list)
        assert len(sources) > 0
        assert "wikipedia.org" in sources or "stackoverflow.com" in sources
    
    def test_plan_learning_steps(self):
        """Test learning step planning."""
        steps = self.engine._plan_learning_steps("Machine Learning")
        
        assert isinstance(steps, list)
        assert len(steps) > 0
        assert any("recherch" in step.lower() for step in steps)
    
    def test_get_stats(self):
        """Test statistics generation."""
        # Create some goals
        gaps = self.engine.identify_knowledge_gaps()
        self.engine.prioritize_goals(gaps)
        
        stats = self.engine.get_stats()
        
        assert "total_goals" in stats
        assert "by_status" in stats
        assert "by_gap_type" in stats
        assert "avg_priority" in stats
        assert isinstance(stats["total_goals"], int)
        assert stats["total_goals"] > 0
    
    def test_knowledge_gap_serialization(self):
        """Test that KnowledgeGap serializes correctly."""
        gap = KnowledgeGap(
            topic="Test Topic",
            gap_type="missing",
            evidence=["Test evidence"],
            priority_score=0.8,
            identified_at=123.456
        )
        
        data = gap.to_dict()
        
        assert data["topic"] == "Test Topic"
        assert data["gap_type"] == "missing"
        assert data["priority_score"] == 0.8
    
    def test_learning_goal_serialization(self):
        """Test that LearningGoal serializes correctly."""
        gap = KnowledgeGap(
            topic="Test",
            gap_type="missing",
            evidence=[],
            priority_score=0.5,
            identified_at=123.0
        )
        
        goal = LearningGoal(
            id="test123",
            topic="Test Topic",
            description="Learn about test",
            gap=gap,
            priority=0.8,
            status="pending",
            created_at=123.456
        )
        
        data = goal.to_dict()
        
        assert data["id"] == "test123"
        assert data["topic"] == "Test Topic"
        assert data["status"] == "pending"
        assert "gap" in data
    
    def test_global_singleton(self):
        """Test that get_autonomous_goal_engine returns singleton."""
        e1 = get_autonomous_goal_engine()
        e2 = get_autonomous_goal_engine()
        
        assert e1 is e2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
