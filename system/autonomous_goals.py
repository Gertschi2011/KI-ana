"""
Autonomous Learning Goals System

The AI identifies knowledge gaps and sets its own learning goals.

Process:
1. Identify Knowledge Gaps - What don't I know?
2. Prioritize Goals - What's most important/relevant?
3. Plan Learning Strategy - How do I learn this?
4. Execute & Track - Do it and measure progress
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter


@dataclass
class KnowledgeGap:
    """Represents an identified knowledge gap."""
    topic: str
    gap_type: str  # "missing", "incomplete", "outdated", "high_demand"
    evidence: List[str]  # Why we think this is a gap
    priority_score: float  # 0.0-1.0
    identified_at: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "gap_type": self.gap_type,
            "evidence": self.evidence,
            "priority_score": self.priority_score,
            "identified_at": self.identified_at
        }


@dataclass
class LearningGoal:
    """Represents a learning goal."""
    id: str
    topic: str
    description: str
    gap: KnowledgeGap
    priority: float  # 0.0-1.0
    status: str  # "pending", "in_progress", "completed", "failed"
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Learning strategy
    keywords: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    
    # Progress tracking
    blocks_created: int = 0
    research_attempts: int = 0
    success_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "description": self.description,
            "gap": self.gap.to_dict(),
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "keywords": self.keywords,
            "sources": self.sources,
            "steps": self.steps,
            "blocks_created": self.blocks_created,
            "research_attempts": self.research_attempts,
            "success_rate": self.success_rate
        }


class AutonomousGoalEngine:
    """Engine for autonomous learning goal management."""
    
    def __init__(self):
        self.base_dir = Path.home() / "ki_ana"
        self.runtime_dir = self.base_dir / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        
        self.goals_file = self.runtime_dir / "learning_goals.json"
        self.gaps_file = self.runtime_dir / "knowledge_gaps.json"
        
        self.goals: List[LearningGoal] = []
        self.gaps: List[KnowledgeGap] = []
        
        self._load_state()
    
    def _load_state(self) -> None:
        """Load goals and gaps from disk."""
        try:
            if self.goals_file.exists():
                data = json.loads(self.goals_file.read_text())
                # Deserialize goals properly
                loaded_goals = []
                for g in data:
                    if isinstance(g, dict):
                        # Reconstruct gap if present
                        gap_data = g.get("gap")
                        gap = None
                        if gap_data:
                            gap = KnowledgeGap(
                                topic=gap_data.get("topic", ""),
                                gap_type=gap_data.get("gap_type", "missing"),
                                evidence=gap_data.get("evidence", []),
                                priority_score=gap_data.get("priority_score", 0.5),
                                identified_at=gap_data.get("identified_at", time.time())
                            )
                        
                        # Reconstruct goal
                        goal = LearningGoal(
                            id=g.get("id", ""),
                            topic=g.get("topic", ""),
                            description=g.get("description", ""),
                            gap=gap,
                            priority=g.get("priority", 0.5),
                            status=g.get("status", "pending"),
                            created_at=g.get("created_at", time.time()),
                            keywords=g.get("keywords", []),
                            sources=g.get("sources", []),
                            steps=g.get("steps", [])
                        )
                        loaded_goals.append(goal)
                self.goals = loaded_goals
            
            if self.gaps_file.exists():
                data = json.loads(self.gaps_file.read_text())
                # Deserialize gaps properly
                loaded_gaps = []
                for g in data:
                    if isinstance(g, dict):
                        gap = KnowledgeGap(
                            topic=g.get("topic", ""),
                            gap_type=g.get("gap_type", "missing"),
                            evidence=g.get("evidence", []),
                            priority_score=g.get("priority_score", 0.5),
                            identified_at=g.get("identified_at", time.time())
                        )
                        loaded_gaps.append(gap)
                self.gaps = loaded_gaps
        except Exception as e:
            print(f"Error loading autonomous goals state: {e}")
            pass
    
    def _save_state(self) -> None:
        """Save goals and gaps to disk."""
        try:
            goals_data = [g.to_dict() if hasattr(g, 'to_dict') else g for g in self.goals]
            self.goals_file.write_text(json.dumps(goals_data, indent=2))
            
            gaps_data = [g.to_dict() if hasattr(g, 'to_dict') else g for g in self.gaps]
            self.gaps_file.write_text(json.dumps(gaps_data, indent=2))
        except Exception:
            pass
    
    def identify_knowledge_gaps(self) -> List[KnowledgeGap]:
        """
        Identify knowledge gaps by analyzing:
        1. Unanswered questions (chat history)
        2. Topics with low block count
        3. High-demand topics (frequently asked)
        4. Related topics not yet covered
        """
        gaps = []
        
        # Strategy 1: Analyze unanswered questions
        gaps.extend(self._gaps_from_unanswered_questions())
        
        # Strategy 2: Find high-demand but low-coverage topics
        gaps.extend(self._gaps_from_demand_vs_coverage())
        
        # Strategy 3: Find related topics not covered
        gaps.extend(self._gaps_from_related_topics())
        
        # Deduplicate by topic
        seen_topics = set()
        unique_gaps = []
        for gap in gaps:
            if gap.topic not in seen_topics:
                seen_topics.add(gap.topic)
                unique_gaps.append(gap)
        
        self.gaps = unique_gaps
        self._save_state()
        
        return unique_gaps
    
    def _gaps_from_unanswered_questions(self) -> List[KnowledgeGap]:
        """Find gaps from questions that couldn't be answered."""
        gaps = []
        
        # This would analyze chat logs for failed queries
        # For MVP, we'll use a simplified version
        
        # Common topics that often have questions
        common_questions = [
            "Künstliche Intelligenz Grundlagen",
            "Machine Learning Algorithmen",
            "Python Best Practices",
            "Web Development Modern",
            "Data Science Basics"
        ]
        
        for topic in common_questions:
            # Check if we have enough coverage
            # In production: query memory_store
            gap = KnowledgeGap(
                topic=topic,
                gap_type="high_demand",
                evidence=["Frequently asked but limited coverage"],
                priority_score=0.7,
                identified_at=time.time()
            )
            gaps.append(gap)
        
        return gaps[:3]  # Return top 3
    
    def _gaps_from_demand_vs_coverage(self) -> List[KnowledgeGap]:
        """Find topics with high demand but low coverage."""
        gaps = []
        
        # This would analyze:
        # 1. Search frequency per topic
        # 2. Number of blocks per topic
        # 3. Quality/depth of existing blocks
        
        # Simplified for MVP
        high_demand_topics = {
            "Quantencomputing": 0.8,
            "Blockchain Technologie": 0.75,
            "Climate Change Solutions": 0.85,
            "Renewable Energy": 0.8
        }
        
        for topic, priority in high_demand_topics.items():
            gap = KnowledgeGap(
                topic=topic,
                gap_type="incomplete",
                evidence=["High demand, insufficient coverage"],
                priority_score=priority,
                identified_at=time.time()
            )
            gaps.append(gap)
        
        return gaps[:2]
    
    def _gaps_from_related_topics(self) -> List[KnowledgeGap]:
        """Find related topics not yet covered."""
        gaps = []
        
        # This would use embeddings/knowledge graph
        # For MVP: hardcoded relationships
        
        related_topics = [
            "Neural Networks Architectures",
            "Transformer Models",
            "Natural Language Processing"
        ]
        
        for topic in related_topics:
            gap = KnowledgeGap(
                topic=topic,
                gap_type="missing",
                evidence=["Related to existing knowledge, not yet covered"],
                priority_score=0.6,
                identified_at=time.time()
            )
            gaps.append(gap)
        
        return gaps[:2]
    
    def prioritize_goals(self, gaps: List[KnowledgeGap]) -> List[LearningGoal]:
        """
        Prioritize knowledge gaps into learning goals.
        
        Factors:
        1. User demand (how often asked?)
        2. Relevance to core identity
        3. Feasibility (can we research this?)
        4. Timeliness (is it urgent?)
        """
        goals = []
        
        for gap in gaps:
            # Calculate final priority
            priority = gap.priority_score
            
            # Boost if aligns with core identity
            if self._aligns_with_core_identity(gap.topic):
                priority = min(1.0, priority + 0.1)
            
            # Boost if feasible to research
            if self._is_researchable(gap.topic):
                priority = min(1.0, priority + 0.05)
            
            # Create goal
            goal = LearningGoal(
                id=f"goal_{int(time.time())}_{hash(gap.topic) % 10000}",
                topic=gap.topic,
                description=f"Learn about {gap.topic} to fill knowledge gap",
                gap=gap,
                priority=priority,
                status="pending",
                created_at=time.time()
            )
            
            # Plan learning strategy
            goal.keywords = self._generate_keywords(gap.topic)
            goal.sources = self._suggest_sources(gap.topic)
            goal.steps = self._plan_learning_steps(gap.topic)
            
            goals.append(goal)
        
        # Sort by priority (highest first)
        goals.sort(key=lambda g: g.priority, reverse=True)
        
        self.goals.extend(goals)
        self._save_state()
        
        return goals
    
    def _aligns_with_core_identity(self, topic: str) -> bool:
        """Check if topic aligns with core identity/values."""
        core_keywords = [
            "ki", "artificial intelligence", "machine learning",
            "technologie", "technology", "wissenschaft", "science",
            "bildung", "education", "hilfe", "help"
        ]
        topic_lower = topic.lower()
        return any(kw in topic_lower for kw in core_keywords)
    
    def _is_researchable(self, topic: str) -> bool:
        """Check if topic is feasibly researchable."""
        # Most topics are researchable in modern web
        # Exceptions: very obscure, fictional, or nonsensical
        nonsensical = ["magic", "impossible", "fantasy", "imaginary"]
        topic_lower = topic.lower()
        return not any(ns in topic_lower for ns in nonsensical)
    
    def _generate_keywords(self, topic: str) -> List[str]:
        """Generate search keywords for topic."""
        # Simple keyword generation
        # In production: use NLP/LLM
        keywords = [topic]
        
        # Add common suffixes
        keywords.append(f"{topic} Grundlagen")
        keywords.append(f"{topic} Erklärung")
        keywords.append(f"{topic} Tutorial")
        keywords.append(f"Was ist {topic}")
        
        return keywords[:5]
    
    def _suggest_sources(self, topic: str) -> List[str]:
        """Suggest good sources for this topic."""
        sources = [
            "wikipedia.org",
            "britannica.com"
        ]
        
        # Topic-specific sources
        if "programmier" in topic.lower() or "code" in topic.lower():
            sources.extend(["stackoverflow.com", "github.com"])
        elif "wissenschaft" in topic.lower() or "science" in topic.lower():
            sources.extend(["nature.com", "science.org"])
        
        return sources
    
    def _plan_learning_steps(self, topic: str) -> List[str]:
        """Plan concrete learning steps."""
        return [
            f"1. Recherchiere Grundlagen zu '{topic}'",
            f"2. Sammle 3-5 verlässliche Quellen",
            f"3. Erstelle Zusammenfassung",
            f"4. Identifiziere Unterthemen",
            f"5. Erweitere Wissen zu Unterthemen"
        ]
    
    def get_top_goals(self, n: int = 3) -> List[LearningGoal]:
        """Get top N learning goals by priority."""
        pending = [g for g in self.goals if isinstance(g, LearningGoal) and g.status == "pending"]
        return sorted(pending, key=lambda g: g.priority, reverse=True)[:n]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about autonomous goals."""
        if not self.goals:
            return {
                "total_goals": 0,
                "by_status": {},
                "by_gap_type": {},
                "avg_priority": 0.0
            }
        
        total = len(self.goals)
        by_status = Counter(g.status if isinstance(g, LearningGoal) else g.get("status", "unknown") for g in self.goals)
        
        # Calculate gap types
        by_gap_type = Counter()
        for g in self.goals:
            if isinstance(g, LearningGoal):
                by_gap_type[g.gap.gap_type] += 1
            elif isinstance(g, dict) and "gap" in g:
                gap_type = g["gap"].get("gap_type", "unknown")
                by_gap_type[gap_type] += 1
        
        # Average priority
        priorities = []
        for g in self.goals:
            if isinstance(g, LearningGoal):
                priorities.append(g.priority)
            elif isinstance(g, dict):
                priorities.append(g.get("priority", 0.5))
        
        avg_priority = sum(priorities) / len(priorities) if priorities else 0.0
        
        return {
            "total_goals": total,
            "by_status": dict(by_status),
            "by_gap_type": dict(by_gap_type),
            "avg_priority": avg_priority,
            "top_priority_goal": self.get_top_goals(1)[0].to_dict() if self.get_top_goals(1) else None
        }


# Global instance
_autonomous_goal_engine = AutonomousGoalEngine()


def get_autonomous_goal_engine() -> AutonomousGoalEngine:
    """Get global autonomous goal engine instance."""
    return _autonomous_goal_engine
