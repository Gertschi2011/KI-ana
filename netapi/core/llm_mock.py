"""
Mock LLM Backend for Development & Testing

Provides a drop-in replacement for llm_local when real LLM is unavailable.
Useful for:
- Development without Ollama
- Testing pipeline logic
- Low-resource environments

Usage:
    from netapi.core import llm_mock as llm_local
    response = llm_local.chat_once("What is 2+2?")
"""

from __future__ import annotations
import re
import random
from typing import Iterator, Optional


def available() -> bool:
    """Always returns True (mock is always available)"""
    return True


def chat_once(user: str, system: str = "", *, model: Optional[str] = None, json_response: bool = False) -> Optional[str]:
    """
    Mock LLM response with simple pattern matching.
    
    Provides reasonable answers for common question types:
    - Math calculations
    - Simple facts
    - Yes/no questions
    - Greetings
    """
    user_lower = user.lower()
    
    # Math questions
    math_match = re.search(r'(\d+)\s*\+\s*(\d+)', user)
    if math_match:
        a, b = int(math_match.group(1)), int(math_match.group(2))
        return f"{a} + {b} = {a+b}"
    
    math_match = re.search(r'(\d+)\s*\*\s*(\d+)', user)
    if math_match:
        a, b = int(math_match.group(1)), int(math_match.group(2))
        return f"{a} × {b} = {a*b}"
    
    # Simple commands
    if "sage" in user_lower and "ok" in user_lower:
        return "OK"
    
    if "antworte" in user_lower and ("ja" in user_lower or "nein" in user_lower):
        if "ja" in user_lower:
            return "Ja"
        else:
            return "Nein"
    
    # Colors
    if "farbe" in user_lower or "nenne eine farbe" in user_lower:
        colors = ["Blau", "Rot", "Grün", "Gelb", "Orange", "Violett"]
        return random.choice(colors)
    
    # Greetings
    if any(g in user_lower for g in ["hallo", "hi", "guten tag", "hey"]):
        return "Hallo! Wie kann ich dir helfen?"
    
    # Questions about AI
    if "was bist du" in user_lower or "wer bist du" in user_lower:
        return "Ich bin KI_ana, ein selbstlernender KI-Assistent. (Hinweis: Mock-Modus - echter LLM wird geladen wenn Server bereit ist)"
    
    # Python questions
    if "python" in user_lower and ("was ist" in user_lower or "erklär" in user_lower):
        return "Python ist eine vielseitige Programmiersprache, bekannt für ihre Lesbarkeit und breite Anwendung in Webentwicklung, Data Science und KI."
    
    # JSON response for evaluations
    if json_response and "bewerte" in user_lower:
        return '{"scores": {"correctness": 8, "relevance": 8, "completeness": 7, "clarity": 8, "safety": 10}, "confidence": 0.8, "suggestions": []}'
    
    # Default: Contextual response based on system prompt
    if system and "bewert" in system.lower():
        # Evaluation request
        return '{"scores": {"correctness": 7, "relevance": 8, "completeness": 7, "clarity": 8, "safety": 10}, "confidence": 0.7, "suggestions": ["Mehr Details hinzufügen"]}'
    
    if system and "kurz" in system.lower():
        return "Das ist eine Mock-Antwort. Der echte LLM wird geladen sobald der Server bereit ist."
    
    # Fallback
    return f"Mock-Antwort auf: '{user[:50]}...' (Echter LLM in Vorbereitung)"


def chat_stream(user: str, system: str = "", *, model: Optional[str] = None) -> Iterator[str]:
    """Mock streaming response"""
    response = chat_once(user, system, model=model)
    if response:
        # Simulate streaming by yielding word by word
        words = response.split()
        for word in words:
            yield word + " "


# Compatibility
OLLAMA_HOST = "http://mock:11434"
OLLAMA_MODEL = "mock-model"


if __name__ == "__main__":
    # Self-test
    print("=== Mock LLM Self-Test ===\n")
    
    tests = [
        "Was ist 5+3?",
        "Nenne eine Farbe",
        "Sage OK",
        "Was ist Python?",
        "Hallo",
    ]
    
    for q in tests:
        print(f"Q: {q}")
        print(f"A: {chat_once(q)}\n")
