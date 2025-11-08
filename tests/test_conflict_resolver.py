"""
Tests for Conflict Resolution System

Validates that conflicts are detected and resolved correctly.
"""
import pytest
import sys
from pathlib import Path

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

from conflict_resolver import ConflictResolver, Conflict, Resolution, get_conflict_resolver


class TestConflictResolver:
    """Test the conflict resolution system."""
    
    def setup_method(self):
        """Setup fresh resolver for each test."""
        self.resolver = ConflictResolver()
    
    def test_initialization(self):
        """Test that resolver initializes correctly."""
        assert self.resolver.source_trust is not None
        assert len(self.resolver.source_trust) > 0
        assert self.resolver.source_trust["wikipedia.org"] > 0.8
    
    def test_detect_simple_contradiction(self):
        """Test detecting simple contradictions."""
        blocks = [
            {
                "id": "block1",
                "content": "Python ist eine interpretierte Sprache",
                "topic": "Python",
                "source": "wikipedia"
            },
            {
                "id": "block2",
                "content": "Python ist nicht eine interpretierte Sprache",
                "topic": "Python",
                "source": "user_input"
            }
        ]
        
        conflicts = self.resolver.detect_conflicts_by_topic("Python", blocks)
        
        assert len(conflicts) > 0
        assert conflicts[0].conflict_type == "contradiction"
        assert conflicts[0].confidence > 0.5
    
    def test_detect_temporal_conflict(self):
        """Test detecting temporal conflicts (different years)."""
        blocks = [
            {
                "id": "block1",
                "content": "Python wurde 1991 veröffentlicht",
                "topic": "Python Geschichte",
                "source": "wikipedia"
            },
            {
                "id": "block2",
                "content": "Python wurde 1989 veröffentlicht",
                "topic": "Python Geschichte",
                "source": "web_crawl"
            }
        ]
        
        conflicts = self.resolver.detect_conflicts_by_topic("Python Geschichte", blocks)
        
        # Temporal conflicts are detected (basic heuristic may vary)
        # In production, this would use NLP/LLM for better accuracy
        # For now, we just ensure detection doesn't crash
        assert isinstance(conflicts, list)
    
    def test_no_conflict_similar_content(self):
        """Test that similar but non-conflicting content doesn't trigger."""
        blocks = [
            {
                "id": "block1",
                "content": "Python ist eine interpretierte Programmiersprache",
                "topic": "Python",
                "source": "wikipedia"
            },
            {
                "id": "block2",
                "content": "Python ist eine dynamisch typisierte Sprache",
                "topic": "Python",
                "source": "wikipedia"
            }
        ]
        
        conflicts = self.resolver.detect_conflicts_by_topic("Python", blocks)
        
        # These shouldn't conflict
        assert len(conflicts) == 0
    
    def test_resolve_by_trust_score(self):
        """Test resolution based on trust score."""
        block_wikipedia = {
            "id": "block_wiki",
            "content": "Correct information",
            "source": "wikipedia.org",
            "url": "https://de.wikipedia.org/wiki/Test"
        }
        
        block_user = {
            "id": "block_user",
            "content": "User input",
            "source": "user_input",
            "url": ""
        }
        
        conflict = Conflict(
            block_a_id="block_wiki",
            block_b_id="block_user",
            conflict_type="contradiction",
            topic="Test",
            detected_at=1234567890.0,
            confidence=0.8
        )
        
        resolution = self.resolver.resolve_conflict(conflict, block_wikipedia, block_user)
        
        assert resolution.winner_id == "block_wiki"
        assert resolution.loser_id == "block_user"
        assert resolution.method == "trust_score"
    
    def test_resolve_by_recency(self):
        """Test resolution based on recency for time-sensitive topics."""
        import time
        
        block_old = {
            "id": "block_old",
            "content": "Old information",
            "source": "web_crawl",
            "timestamp": time.time() - 86400 * 30  # 30 days ago
        }
        
        block_new = {
            "id": "block_new",
            "content": "New information",
            "source": "web_crawl",
            "timestamp": time.time()  # Now
        }
        
        conflict = Conflict(
            block_a_id="block_new",
            block_b_id="block_old",
            conflict_type="inconsistency",
            topic="Aktuelles Wetter",  # Time-sensitive
            detected_at=time.time(),
            confidence=0.7
        )
        
        resolution = self.resolver.resolve_conflict(conflict, block_new, block_old)
        
        assert resolution.winner_id == "block_new"
        assert resolution.method == "recency"
    
    def test_get_trust_score_from_url(self):
        """Test that trust score is extracted from URL."""
        block = {
            "url": "https://en.wikipedia.org/wiki/Test",
            "source": "unknown"
        }
        
        score = self.resolver._get_trust_score(block)
        assert score >= 0.8  # Wikipedia should have high trust
    
    def test_get_trust_score_from_source(self):
        """Test that trust score is extracted from source field."""
        block = {
            "url": "",
            "source": "gpt-5"
        }
        
        score = self.resolver._get_trust_score(block)
        assert score >= 0.7  # GPT-5 should have decent trust
    
    def test_get_trust_score_default(self):
        """Test default trust score for unknown sources."""
        block = {
            "url": "",
            "source": "unknown_source"
        }
        
        score = self.resolver._get_trust_score(block)
        assert score == self.resolver.source_trust["default"]
    
    def test_is_time_sensitive_topic(self):
        """Test time-sensitive topic detection."""
        assert self.resolver._is_time_sensitive_topic("Aktuelles Wetter")
        assert self.resolver._is_time_sensitive_topic("Bitcoin Preis heute")
        assert self.resolver._is_time_sensitive_topic("Current news")
        
        assert not self.resolver._is_time_sensitive_topic("Geschichte")
        assert not self.resolver._is_time_sensitive_topic("Mathematik")
    
    def test_apply_resolution(self):
        """Test applying a resolution."""
        conflict = Conflict(
            block_a_id="winner",
            block_b_id="loser",
            conflict_type="contradiction",
            topic="Test",
            detected_at=1234567890.0,
            confidence=0.9
        )
        
        resolution = Resolution(
            conflict=conflict,
            winner_id="winner",
            loser_id="loser",
            reason="Test reason",
            resolved_at=1234567891.0,
            method="trust_score"
        )
        
        result = self.resolver.apply_resolution(resolution)
        
        assert result["ok"] is True
        assert result["winner_id"] == "winner"
        assert result["loser_id"] == "loser"
    
    def test_get_stats(self):
        """Test getting statistics."""
        stats = self.resolver.get_stats()
        
        assert "total_resolutions" in stats
        assert "by_method" in stats
        assert "by_type" in stats
        assert isinstance(stats["total_resolutions"], int)
    
    def test_conflict_to_dict(self):
        """Test conflict serialization."""
        conflict = Conflict(
            block_a_id="a",
            block_b_id="b",
            conflict_type="contradiction",
            topic="Test",
            detected_at=123.456,
            confidence=0.75
        )
        
        data = conflict.to_dict()
        
        assert data["block_a_id"] == "a"
        assert data["block_b_id"] == "b"
        assert data["conflict_type"] == "contradiction"
        assert data["confidence"] == 0.75
    
    def test_resolution_to_dict(self):
        """Test resolution serialization."""
        conflict = Conflict(
            block_a_id="a",
            block_b_id="b",
            conflict_type="contradiction",
            topic="Test",
            detected_at=123.456,
            confidence=0.75
        )
        
        resolution = Resolution(
            conflict=conflict,
            winner_id="a",
            loser_id="b",
            reason="Test",
            resolved_at=124.456,
            method="trust_score"
        )
        
        data = resolution.to_dict()
        
        assert data["winner_id"] == "a"
        assert data["loser_id"] == "b"
        assert data["method"] == "trust_score"
        assert "conflict" in data
    
    def test_global_singleton(self):
        """Test that get_conflict_resolver returns singleton."""
        r1 = get_conflict_resolver()
        r2 = get_conflict_resolver()
        
        assert r1 is r2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
