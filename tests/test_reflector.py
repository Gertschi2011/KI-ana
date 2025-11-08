"""
Unit tests for Reflector module
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from netapi.core.reflector import (
    ResponseReflector,
    reflect_on_response,
    QualityDimension,
    EvaluationResult
)


class TestReflector:
    """Test suite for ResponseReflector"""
    
    def test_reflector_initialization(self):
        """Test that reflector initializes correctly"""
        reflector = ResponseReflector(llm_backend=None, quality_threshold=0.7)
        assert reflector.quality_threshold == 0.7
        assert len(reflector._evaluation_history) == 0
    
    def test_heuristic_evaluation_good_answer(self):
        """Test heuristic evaluation with a good answer"""
        evaluation = reflect_on_response(
            question="Was ist 2+2?",
            answer="2+2 ist 4. Dies ist eine einfache Addition."
        )
        
        assert evaluation.overall_score > 0.5
        assert not evaluation.needs_retry
        assert isinstance(evaluation.dimension_scores, dict)
    
    def test_heuristic_evaluation_bad_answer(self):
        """Test heuristic evaluation with irrelevant answer"""
        evaluation = reflect_on_response(
            question="Was ist 2+2?",
            answer="TL;DR: Das Coupé ist ein französischer Wagen."
        )
        
        # Should detect this as bad (low correctness due to known pattern)
        assert evaluation.dimension_scores.get("correctness", 1.0) < 0.5
        assert len(evaluation.suggestions) > 0
    
    def test_heuristic_evaluation_uncertain_answer(self):
        """Test detection of uncertainty in answers"""
        evaluation = reflect_on_response(
            question="Wie alt ist das Universum?",
            answer="Ich bin nicht sicher, möglicherweise 13 Milliarden Jahre."
        )
        
        # Should detect uncertainty
        assert evaluation.dimension_scores.get("correctness", 1.0) < 0.8
        assert any("Unsicherheit" in s for s in evaluation.suggestions)
    
    def test_should_retry_logic(self):
        """Test retry decision logic"""
        reflector = ResponseReflector(quality_threshold=0.7)
        
        # Low overall score should trigger retry
        eval_low = EvaluationResult(
            overall_score=0.5,
            dimension_scores={"correctness": 0.5},
            confidence=0.6,
            needs_retry=True,
            suggestions=["Improve quality"],
            timestamp=0
        )
        should_retry, reason = reflector.should_retry(eval_low)
        assert should_retry
        assert "threshold" in reason.lower()
        
        # High score should not trigger retry
        eval_high = EvaluationResult(
            overall_score=0.9,
            dimension_scores={"correctness": 0.9},
            confidence=0.9,
            needs_retry=False,
            suggestions=[],
            timestamp=0
        )
        should_retry, reason = reflector.should_retry(eval_high)
        assert not should_retry
    
    def test_critical_dimension_retry(self):
        """Test that critical dimensions trigger retry even if overall OK"""
        reflector = ResponseReflector(quality_threshold=0.7)
        
        # Overall good but safety critical
        eval_unsafe = EvaluationResult(
            overall_score=0.75,
            dimension_scores={
                "correctness": 0.9,
                "relevance": 0.9,
                "safety": 0.3  # Critical!
            },
            confidence=0.8,
            needs_retry=False,
            suggestions=[],
            timestamp=0
        )
        
        should_retry, reason = reflector.should_retry(eval_unsafe)
        assert should_retry
        assert "safety" in reason.lower()
    
    def test_improvement_prompt_generation(self):
        """Test generation of improvement prompts"""
        reflector = ResponseReflector()
        
        evaluation = EvaluationResult(
            overall_score=0.6,
            dimension_scores={"correctness": 0.5, "completeness": 0.6},
            confidence=0.7,
            needs_retry=True,
            suggestions=["Add more details", "Verify facts"],
            timestamp=0
        )
        
        prompt = reflector.generate_improvement_prompt(
            evaluation,
            "Was ist Python?"
        )
        
        assert "Was ist Python?" in prompt
        assert "correctness" in prompt or "completeness" in prompt
        assert len(prompt) > 50
    
    def test_statistics_tracking(self):
        """Test that statistics are tracked correctly"""
        reflector = ResponseReflector()
        
        # Add some evaluations
        for i in range(5):
            score = 0.5 + (i * 0.1)  # 0.5, 0.6, 0.7, 0.8, 0.9
            reflector._evaluation_history.append(
                EvaluationResult(
                    overall_score=score,
                    dimension_scores={},
                    confidence=0.8,
                    needs_retry=(score < 0.7),
                    suggestions=[],
                    timestamp=i
                )
            )
        
        stats = reflector.get_statistics()
        
        assert stats["total_evaluations"] == 5
        assert 0.6 < stats["average_score"] < 0.8  # Average of 0.5-0.9
        assert stats["retry_rate"] == 0.4  # 2 out of 5 need retry


class TestEvaluationResult:
    """Test EvaluationResult dataclass"""
    
    def test_to_dict(self):
        """Test serialization to dict"""
        result = EvaluationResult(
            overall_score=0.85,
            dimension_scores={"correctness": 0.9, "relevance": 0.8},
            confidence=0.9,
            needs_retry=False,
            suggestions=["Good job"],
            timestamp=123456
        )
        
        d = result.to_dict()
        
        assert d["overall_score"] == 0.85
        assert d["confidence"] == 0.9
        assert d["needs_retry"] is False
        assert len(d["suggestions"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
