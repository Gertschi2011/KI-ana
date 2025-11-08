"""
KI-ana OS - Natural Language Processing

Advanced NLP with LLM integration.
"""

from .llm_client import LLMClient
from .intent_llm import LLMIntentRecognizer
from .response_generator import ResponseGenerator

__all__ = ["LLMClient", "LLMIntentRecognizer", "ResponseGenerator"]
