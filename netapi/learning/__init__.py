"""
Learning Module for KI_ana

Implements continuous learning mechanisms:
- Feedback learning
- Tool success tracking
- Pattern recognition
- Reinforcement learning

Part of Phase 2: Continuous Learning
"""

from .hub import LearningHub, get_learning_hub, Interaction, ToolStatistics

__all__ = ["LearningHub", "get_learning_hub", "Interaction", "ToolStatistics"]
