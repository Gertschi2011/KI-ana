"""
Skills Module - Autonomous Tool Generation

Enables the AI to generate and integrate new capabilities.
"""
from .skill_engine import SkillEngine, SkillSpec, GeneratedSkill, get_skill_engine

__all__ = [
    "SkillEngine",
    "SkillSpec",
    "GeneratedSkill",
    "get_skill_engine",
]
