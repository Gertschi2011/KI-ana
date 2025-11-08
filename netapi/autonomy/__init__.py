"""
Autonomy Module for KI_ana

Implements autonomous decision-making and planning:
- Decision Engine (multi-step planning)
- Goal analysis
- Tool orchestration

Part of Phase 3: Autonomie
"""

from .decision_engine import DecisionEngine, get_decision_engine, ExecutionPlan, Task

__all__ = ["DecisionEngine", "get_decision_engine", "ExecutionPlan", "Task"]
