"""
Learning Hub - Continuous Learning System for KI_ana

Implements various learning mechanisms to improve AI performance over time:
1. Feedback Learning - Learn from user corrections and ratings
2. Tool Success Tracking - Optimize tool selection based on success rates
3. Pattern Recognition - Identify common question types and optimal responses
4. Reinforcement Learning - Simple reward-based learning

This module is part of Phase 2 of the KI_ana Vision (Continuous Learning).
"""

from __future__ import annotations
import time
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import os


@dataclass
class Interaction:
    """Record of a single user-AI interaction"""
    timestamp: int
    question: str
    answer: str
    quality_score: float
    tools_used: List[str]
    retry_count: int
    user_feedback: Optional[str] = None  # "positive", "negative", "neutral"
    user_correction: Optional[str] = None  # What user said the answer should be
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "question": self.question,
            "answer": self.answer,
            "quality_score": self.quality_score,
            "tools_used": self.tools_used,
            "retry_count": self.retry_count,
            "user_feedback": self.user_feedback,
            "user_correction": self.user_correction,
        }


@dataclass
class ToolStatistics:
    """Statistics for a single tool"""
    name: str
    total_uses: int = 0
    successes: int = 0
    failures: int = 0
    avg_response_time_ms: float = 0.0
    last_success_rate: float = 0.0
    
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_uses == 0:
            return 0.5  # Default: assume 50% if no data
        return self.successes / self.total_uses
    
    def update(self, success: bool, response_time_ms: float):
        """Update statistics after tool use"""
        self.total_uses += 1
        if success:
            self.successes += 1
        else:
            self.failures += 1
        
        # Update running average of response time
        alpha = 0.1  # Smoothing factor
        self.avg_response_time_ms = (
            alpha * response_time_ms + 
            (1 - alpha) * self.avg_response_time_ms
        )
        
        self.last_success_rate = self.success_rate()


class LearningHub:
    """
    Central learning system for KI_ana.
    
    Tracks interactions, learns from feedback, and improves decision-making.
    
    Usage:
        hub = LearningHub()
        
        # Record interaction
        hub.record_interaction(
            question="Was ist 2+2?",
            answer="4",
            quality_score=0.95,
            tools_used=["calc"]
        )
        
        # Add user feedback
        hub.add_feedback(interaction_id, "positive")
        
        # Get tool recommendations
        best_tools = hub.recommend_tools_for_question("Was ist...")
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Args:
            storage_path: Path to store learning data (default: ~/ki_ana/learning)
        """
        if storage_path is None:
            storage_path = str(Path.home() / "ki_ana" / "learning")
        
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory caches
        self.interactions: List[Interaction] = []
        self.tool_stats: Dict[str, ToolStatistics] = {}
        self.question_patterns: Dict[str, List[str]] = defaultdict(list)  # pattern -> [best tools]
        
        # Load existing data
        self._load_from_disk()

        # If a hub is explicitly constructed (e.g., tests), make it the global instance
        # so other components (MetaMind/ResponsePipeline defaults) can read its stats.
        global _hub_instance
        _hub_instance = self
    
    def record_interaction(
        self,
        question: str,
        answer: str,
        quality_score: float,
        tools_used: List[str],
        retry_count: int = 0
    ) -> str:
        """
        Record a new interaction for learning.
        
        Returns:
            interaction_id (timestamp as string)
        """
        interaction = Interaction(
            timestamp=int(time.time()),
            question=question,
            answer=answer,
            quality_score=quality_score,
            tools_used=tools_used,
            retry_count=retry_count
        )
        
        self.interactions.append(interaction)
        
        # Learn from this interaction
        self._learn_from_interaction(interaction)
        
        # Persist periodically
        if len(self.interactions) % 10 == 0:
            self._save_to_disk()
        
        return str(interaction.timestamp)
    
    def add_feedback(
        self,
        interaction_id: str,
        feedback: str,
        correction: Optional[str] = None
    ):
        """
        Add user feedback to a past interaction.
        
        Args:
            interaction_id: Timestamp from record_interaction
            feedback: "positive", "negative", or "neutral"
            correction: Optional corrected answer
        """
        # Find interaction
        timestamp = int(interaction_id)
        interaction = None
        for i in self.interactions:
            if i.timestamp == timestamp:
                interaction = i
                break
        
        if not interaction:
            return
        
        interaction.user_feedback = feedback
        interaction.user_correction = correction
        
        # Learn from feedback
        if feedback == "negative" and correction:
            self._learn_from_correction(interaction, correction)
        
        self._save_to_disk()
    
    def record_tool_use(
        self,
        tool_name: str,
        success: bool,
        response_time_ms: float
    ):
        """
        Record tool usage statistics.
        
        Args:
            tool_name: Name of the tool
            success: Whether tool succeeded
            response_time_ms: How long it took
        """
        if tool_name not in self.tool_stats:
            self.tool_stats[tool_name] = ToolStatistics(name=tool_name)
        
        self.tool_stats[tool_name].update(success, response_time_ms)
    
    def recommend_tools_for_question(
        self,
        question: str,
        top_k: int = 3
    ) -> List[Tuple[str, float]]:
        """
        Recommend best tools for a question based on learning.
        
        Returns:
            List of (tool_name, confidence_score) tuples
        """
        # Pattern matching based on learned patterns
        q_lower = question.lower()
        
        # Check learned patterns
        scores: Dict[str, float] = defaultdict(float)
        
        for pattern, tools in self.question_patterns.items():
            if pattern in q_lower:
                for tool in tools:
                    # Tool success rate as base score
                    if tool in self.tool_stats:
                        scores[tool] += self.tool_stats[tool].success_rate()
        
        # If no learned patterns, use overall tool success rates
        if not scores:
            for tool_name, stats in self.tool_stats.items():
                scores[tool_name] = stats.success_rate()
        
        # Sort by score
        sorted_tools = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        return sorted_tools[:top_k]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall learning statistics"""
        if not self.interactions:
            return {
                "total_interactions": 0,
                "avg_quality": 0.0,
                "positive_feedback_rate": 0.0,
                "tools": {}
            }
        
        total = len(self.interactions)
        avg_quality = sum(i.quality_score for i in self.interactions) / total
        
        feedback_count = sum(1 for i in self.interactions if i.user_feedback)
        positive_count = sum(1 for i in self.interactions if i.user_feedback == "positive")
        positive_rate = positive_count / feedback_count if feedback_count > 0 else 0.0
        
        tool_stats = {
            name: {
                "uses": stats.total_uses,
                "success_rate": stats.success_rate(),
                "avg_time_ms": stats.avg_response_time_ms
            }
            for name, stats in self.tool_stats.items()
        }
        
        return {
            "total_interactions": total,
            "avg_quality": round(avg_quality, 3),
            "positive_feedback_rate": round(positive_rate, 3),
            "feedback_count": feedback_count,
            "tools": tool_stats,
            "learned_patterns": len(self.question_patterns)
        }
    
    def _learn_from_interaction(self, interaction: Interaction):
        """Extract learning from successful interaction"""
        # If high quality, remember which tools worked for this question type
        if interaction.quality_score >= 0.8:
            # Extract pattern (simplified - first 3 words)
            words = interaction.question.lower().split()[:3]
            pattern = " ".join(words)
            
            if pattern and interaction.tools_used:
                self.question_patterns[pattern] = interaction.tools_used
    
    def _learn_from_correction(self, interaction: Interaction, correction: str):
        """Learn from user correction"""
        # Store correction as training data for future improvement
        # This will be used when we implement fine-tuning
        
        correction_file = self.storage_path / "corrections.jsonl"
        with open(correction_file, "a") as f:
            data = {
                "question": interaction.question,
                "wrong_answer": interaction.answer,
                "correct_answer": correction,
                "timestamp": int(time.time())
            }
            f.write(json.dumps(data) + "\n")
    
    def _save_to_disk(self):
        """Persist learning data"""
        try:
            # Save interactions (last 1000 only to limit file size)
            interactions_file = self.storage_path / "interactions.json"
            data = [i.to_dict() for i in self.interactions[-1000:]]
            with open(interactions_file, "w") as f:
                json.dump(data, f, indent=2)
            
            # Save tool stats
            stats_file = self.storage_path / "tool_stats.json"
            stats_data = {
                name: {
                    "total_uses": s.total_uses,
                    "successes": s.successes,
                    "failures": s.failures,
                    "avg_response_time_ms": s.avg_response_time_ms,
                }
                for name, s in self.tool_stats.items()
            }
            with open(stats_file, "w") as f:
                json.dump(stats_data, f, indent=2)
            
            # Save patterns
            patterns_file = self.storage_path / "patterns.json"
            with open(patterns_file, "w") as f:
                json.dump(dict(self.question_patterns), f, indent=2)
                
        except Exception as e:
            print(f"Failed to save learning data: {e}")
    
    def _load_from_disk(self):
        """Load persisted learning data"""
        try:
            # Load tool stats
            stats_file = self.storage_path / "tool_stats.json"
            if stats_file.exists():
                with open(stats_file) as f:
                    stats_data = json.load(f)
                    for name, data in stats_data.items():
                        self.tool_stats[name] = ToolStatistics(
                            name=name,
                            total_uses=data["total_uses"],
                            successes=data["successes"],
                            failures=data["failures"],
                            avg_response_time_ms=data["avg_response_time_ms"]
                        )
            
            # Load patterns
            patterns_file = self.storage_path / "patterns.json"
            if patterns_file.exists():
                with open(patterns_file) as f:
                    patterns_data = json.load(f)
                    self.question_patterns.update(patterns_data)
                    
        except Exception as e:
            print(f"Failed to load learning data: {e}")


# Global instance
_hub_instance: Optional[LearningHub] = None


def get_learning_hub() -> LearningHub:
    """Get or create global LearningHub instance"""
    global _hub_instance
    if _hub_instance is None:
        _hub_instance = LearningHub()
    return _hub_instance


if __name__ == "__main__":
    # Self-test
    print("=== Learning Hub Self-Test ===\n")
    
    hub = LearningHub(storage_path="/tmp/ki_ana_learning_test")
    
    # Record some interactions
    hub.record_interaction(
        question="Was ist 2+2?",
        answer="4",
        quality_score=0.95,
        tools_used=["calc"]
    )
    
    hub.record_tool_use("calc", success=True, response_time_ms=50)
    hub.record_tool_use("memory", success=False, response_time_ms=200)
    
    hub.record_interaction(
        question="Was ist Python?",
        answer="Eine Programmiersprache",
        quality_score=0.85,
        tools_used=["memory", "web"]
    )
    
    # Get stats
    stats = hub.get_statistics()
    print(f"Statistics: {json.dumps(stats, indent=2)}")
    
    # Recommend tools
    recommendations = hub.recommend_tools_for_question("Was ist JavaScript?")
    print(f"\nRecommended tools: {recommendations}")
