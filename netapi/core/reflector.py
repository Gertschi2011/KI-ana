"""
Self-Reflection Module for KI_ana

Implements meta-cognitive evaluation of AI responses BEFORE they are sent to users.
This is a core component for achieving true AI autonomy and continuous improvement.

Key Features:
- Response quality evaluation (correctness, relevance, completeness)
- Automatic retry trigger for low-quality responses
- Learning from evaluations for future improvements
- Confidence scoring for transparency

Part of Vision: Autonomous, self-learning, self-reflecting AI system
"""

from __future__ import annotations
import json
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum


class QualityDimension(Enum):
    """Dimensions for evaluating response quality"""
    CORRECTNESS = "correctness"      # Factually correct?
    RELEVANCE = "relevance"          # Answers the actual question?
    COMPLETENESS = "completeness"    # Covers all aspects?
    CLARITY = "clarity"              # Easy to understand?
    SAFETY = "safety"                # No harmful content?


@dataclass
class EvaluationResult:
    """Result of a response evaluation"""
    overall_score: float  # 0.0-1.0
    dimension_scores: Dict[str, float]  # Per-dimension scores
    confidence: float  # Evaluator's confidence in its judgment
    needs_retry: bool
    suggestions: List[str]  # Improvement suggestions
    timestamp: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "confidence": self.confidence,
            "needs_retry": self.needs_retry,
            "suggestions": self.suggestions,
            "timestamp": self.timestamp,
        }


class ResponseReflector:
    """
    Meta-cognitive evaluator for AI responses.
    
    Acts as an internal critic that judges response quality BEFORE output,
    similar to human self-reflection before speaking.
    
    Usage:
        reflector = ResponseReflector(llm_backend)
        evaluation = reflector.evaluate(question, answer, context)
        
        if evaluation.needs_retry:
            # Generate improved response
            improved = generate_with_hints(question, evaluation.suggestions)
            evaluation = reflector.evaluate(question, improved, context)
    """
    
    def __init__(self, llm_backend=None, quality_threshold: float = 0.7):
        """
        Args:
            llm_backend: LLM instance for self-evaluation (e.g., llm_local)
            quality_threshold: Minimum score to accept response (0.0-1.0)
        """
        self.llm = llm_backend
        self.quality_threshold = quality_threshold
        self._evaluation_history: List[EvaluationResult] = []
        
    def evaluate(
        self,
        question: str,
        answer: str,
        context: Optional[Dict[str, Any]] = None,
        dimensions: Optional[List[QualityDimension]] = None
    ) -> EvaluationResult:
        """
        Evaluate a generated response across multiple quality dimensions.
        
        Args:
            question: Original user question
            answer: Generated AI response
            context: Additional context (tools used, sources, etc.)
            dimensions: Which dimensions to evaluate (default: all)
            
        Returns:
            EvaluationResult with scores and improvement suggestions
        """
        if dimensions is None:
            dimensions = list(QualityDimension)
        
        # If no LLM available, use heuristic evaluation
        if self.llm is None or not hasattr(self.llm, 'available') or not self.llm.available():
            return self._heuristic_evaluation(question, answer, context)
        
        # Use LLM for meta-evaluation
        return self._llm_evaluation(question, answer, context, dimensions)
    
    def _llm_evaluation(
        self,
        question: str,
        answer: str,
        context: Optional[Dict[str, Any]],
        dimensions: List[QualityDimension]
    ) -> EvaluationResult:
        """
        Use LLM to evaluate response quality (meta-cognition).
        
        The LLM acts as its own critic, judging the quality of its output.
        """
        context_str = self._format_context(context) if context else "Kein zusätzlicher Kontext."
        
        dimension_prompts = {
            QualityDimension.CORRECTNESS: "Ist die Antwort faktisch korrekt? Keine Halluzinationen?",
            QualityDimension.RELEVANCE: "Beantwortet die Antwort wirklich die gestellte Frage?",
            QualityDimension.COMPLETENESS: "Ist die Antwort vollständig oder fehlen wichtige Aspekte?",
            QualityDimension.CLARITY: "Ist die Antwort klar und verständlich formuliert?",
            QualityDimension.SAFETY: "Enthält die Antwort keine schädlichen oder unsicheren Inhalte?",
        }
        
        eval_prompt = f"""Bewerte die folgende KI-Antwort objektiv und selbstkritisch.

FRAGE: {question}

ANTWORT: {answer}

KONTEXT: {context_str}

Bewerte die Antwort auf folgenden Skalen (0-10):
"""
        for dim in dimensions:
            eval_prompt += f"\n- {dim.value}: {dimension_prompts.get(dim, 'Bewerte diesen Aspekt.')}"
        
        eval_prompt += """

Gib auch Verbesserungsvorschläge, falls die Antwort nicht perfekt ist.

Antworte im JSON-Format:
{
  "scores": {"correctness": X, "relevance": Y, "completeness": Z, ...},
  "confidence": 0.0-1.0,
  "suggestions": ["Vorschlag 1", "Vorschlag 2", ...]
}
"""
        
        try:
            response = self.llm.chat_once(eval_prompt, system="Du bist ein objektiver Qualitäts-Evaluator. Sei selbstkritisch.", json_response=True)
            
            if not response:
                return self._heuristic_evaluation(question, answer, context)
            
            # Parse LLM evaluation
            try:
                eval_data = json.loads(response)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    eval_data = json.loads(json_match.group())
                else:
                    return self._heuristic_evaluation(question, answer, context)
            
            scores = eval_data.get("scores", {})
            # Normalize scores from 0-10 to 0-1
            dimension_scores = {k: min(1.0, max(0.0, v / 10.0)) for k, v in scores.items()}
            
            overall = sum(dimension_scores.values()) / max(1, len(dimension_scores))
            confidence = float(eval_data.get("confidence", 0.8))
            suggestions = eval_data.get("suggestions", [])
            
            needs_retry = overall < self.quality_threshold
            
            result = EvaluationResult(
                overall_score=overall,
                dimension_scores=dimension_scores,
                confidence=confidence,
                needs_retry=needs_retry,
                suggestions=suggestions[:5],  # Limit to top 5
                timestamp=int(time.time())
            )
            
            self._evaluation_history.append(result)
            return result
            
        except Exception as e:
            # Fallback to heuristic on any error
            print(f"LLM evaluation failed: {e}, using heuristic fallback")
            return self._heuristic_evaluation(question, answer, context)
    
    def _heuristic_evaluation(
        self,
        question: str,
        answer: str,
        context: Optional[Dict[str, Any]]
    ) -> EvaluationResult:
        """
        Fallback: Simple rule-based evaluation when LLM unavailable.
        
        Not as sophisticated as LLM evaluation, but provides basic quality checks.
        """
        scores = {}
        suggestions = []
        
        # Correctness: Check for common hallucination patterns
        correctness = 0.8  # Default assume correct (optimistic)
        if "ich bin nicht sicher" in answer.lower() or "möglicherweise" in answer.lower():
            correctness = 0.6
            suggestions.append("Antwort enthält Unsicherheit - mehr Quellen prüfen")
        if "tl;dr" in answer.lower() and "coupé" in answer.lower():
            # Detected known bad pattern from current system
            correctness = 0.2
            suggestions.append("Antwort scheint irrelevant (falscher Kontext)")
        scores["correctness"] = correctness
        
        # Relevance: Check if answer relates to question
        question_words = set(question.lower().split())
        answer_words = set(answer.lower().split())
        overlap = len(question_words & answer_words) / max(1, len(question_words))
        relevance = min(1.0, overlap * 2)  # Scale up overlap
        scores["relevance"] = relevance
        
        if relevance < 0.3:
            suggestions.append("Antwort scheint nicht zur Frage zu passen")
        
        # Completeness: Check length relative to question complexity
        question_len = len(question.split())
        answer_len = len(answer.split())
        
        if question_len > 10 and answer_len < 20:
            completeness = 0.5
            suggestions.append("Antwort könnte ausführlicher sein")
        elif answer_len > 500:
            completeness = 0.7
            suggestions.append("Antwort sehr lang - Kernaussage hervorheben")
        else:
            completeness = 0.8
        scores["completeness"] = completeness
        
        # Clarity: Check for clear structure
        clarity = 0.7  # Default
        if answer.count('\n') > 3:  # Has structure
            clarity = 0.9
        if len(answer.split('.')) < 2:  # Very short, might be unclear
            clarity = 0.6
            suggestions.append("Antwort könnte klarer strukturiert sein")
        scores["clarity"] = clarity
        
        # Safety: Basic check for problematic content
        safety = 1.0  # Default safe
        unsafe_patterns = ["wie man", "anleitung zum", "schritt für schritt"]
        if any(pattern in answer.lower() for pattern in unsafe_patterns):
            safety = 0.8  # Flag for manual review
        scores["safety"] = safety
        
        overall = sum(scores.values()) / len(scores)
        needs_retry = overall < self.quality_threshold
        
        if not suggestions:
            if overall < 0.7:
                suggestions.append("Generelle Qualitätsverbesserung empfohlen")
        
        return EvaluationResult(
            overall_score=overall,
            dimension_scores=scores,
            confidence=0.6,  # Lower confidence for heuristic
            needs_retry=needs_retry,
            suggestions=suggestions,
            timestamp=int(time.time())
        )
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context dict into readable string for evaluation"""
        parts = []
        if context.get("tools_used"):
            tools = ", ".join(t.get("tool", "?") for t in context["tools_used"])
            parts.append(f"Tools: {tools}")
        if context.get("sources"):
            sources = ", ".join(s.get("title", "?") for s in context["sources"][:3])
            parts.append(f"Quellen: {sources}")
        return " | ".join(parts) if parts else "Kein Kontext"
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about evaluation history"""
        if not self._evaluation_history:
            return {"total": 0, "average_score": 0.0, "retry_rate": 0.0}
        
        total = len(self._evaluation_history)
        avg_score = sum(e.overall_score for e in self._evaluation_history) / total
        retries = sum(1 for e in self._evaluation_history if e.needs_retry)
        
        return {
            "total_evaluations": total,
            "average_score": round(avg_score, 3),
            "retry_rate": round(retries / total, 3),
            "last_10_avg": round(
                sum(e.overall_score for e in self._evaluation_history[-10:]) / min(10, total),
                3
            ),
        }
    
    def should_retry(self, evaluation: EvaluationResult) -> Tuple[bool, str]:
        """
        Decide if response should be regenerated.
        
        Returns:
            (should_retry, reason)
        """
        if evaluation.overall_score < self.quality_threshold:
            return True, f"Score {evaluation.overall_score:.2f} < threshold {self.quality_threshold}"
        
        # Even if overall OK, retry if critical dimension fails
        critical_dimensions = ["correctness", "safety", "relevance"]
        for dim in critical_dimensions:
            score = evaluation.dimension_scores.get(dim, 1.0)
            if score < 0.5:
                return True, f"Critical dimension '{dim}' too low: {score:.2f}"
        
        return False, "Quality acceptable"
    
    def generate_improvement_prompt(self, evaluation: EvaluationResult, original_question: str) -> str:
        """
        Generate an improved prompt based on evaluation feedback.
        
        This helps the system learn from its mistakes.
        """
        hints = "\n".join(f"- {s}" for s in evaluation.suggestions)
        
        low_dimensions = [
            dim for dim, score in evaluation.dimension_scores.items()
            if score < 0.7
        ]
        
        improvement_prompt = f"""Verbessere die vorherige Antwort.

Ursprüngliche Frage: {original_question}

Die vorherige Antwort hatte Schwächen in: {', '.join(low_dimensions)}

Verbesserungsvorschläge:
{hints}

Generiere eine bessere Antwort, die diese Punkte adressiert. Sei präzise, relevant und vollständig."""
        
        return improvement_prompt


# Global instance (singleton pattern)
_reflector_instance: Optional[ResponseReflector] = None


def get_reflector(llm_backend=None, quality_threshold: float = 0.7) -> ResponseReflector:
    """
    Get or create global Reflector instance.
    
    Args:
        llm_backend: LLM to use for evaluation (only used on first call)
        quality_threshold: Minimum quality score (only used on first call)
    """
    global _reflector_instance
    if _reflector_instance is None:
        _reflector_instance = ResponseReflector(llm_backend, quality_threshold)
    return _reflector_instance


# Convenience function for quick evaluation
def reflect_on_response(
    question: str,
    answer: str,
    context: Optional[Dict[str, Any]] = None,
    llm_backend=None
) -> EvaluationResult:
    """
    Quick helper to evaluate a response.
    
    Usage:
        evaluation = reflect_on_response("Was ist 2+2?", "4")
        if evaluation.needs_retry:
            # Regenerate
    """
    reflector = get_reflector(llm_backend)
    return reflector.evaluate(question, answer, context)


if __name__ == "__main__":
    # Self-test
    print("=== Reflector Self-Test ===\n")
    
    # Test 1: Good answer
    eval1 = reflect_on_response(
        "Was ist 2+2?",
        "2+2 ist 4. Dies ist eine einfache Addition.",
        None
    )
    print(f"Test 1 (Good): Score={eval1.overall_score:.2f}, Retry={eval1.needs_retry}")
    
    # Test 2: Bad answer (irrelevant)
    eval2 = reflect_on_response(
        "Was ist 2+2?",
        "TL;DR: Das Coupé ist ein zweitüriger Wagen.",
        None
    )
    print(f"Test 2 (Bad): Score={eval2.overall_score:.2f}, Retry={eval2.needs_retry}")
    print(f"Suggestions: {eval2.suggestions}")
    
    # Test 3: Uncertain answer
    eval3 = reflect_on_response(
        "Wie alt ist das Universum?",
        "Ich bin nicht sicher, möglicherweise 13-14 Milliarden Jahre.",
        None
    )
    print(f"\nTest 3 (Uncertain): Score={eval3.overall_score:.2f}, Retry={eval3.needs_retry}")
    
    reflector = get_reflector()
    print(f"\nStatistics: {reflector.get_statistics()}")
