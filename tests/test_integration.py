"""
Integration tests - Testing components working together
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from netapi.core.reflector import ResponseReflector
from netapi.core.response_pipeline import ResponsePipeline
from netapi.learning.hub import LearningHub
from netapi.autonomy.decision_engine import DecisionEngine
from netapi.core.meta_mind import MetaMind


class TestIntegration:
    """Test integration between components"""
    
    @pytest.fixture
    def mock_llm(self):
        """Mock LLM backend"""
        class MockLLM:
            def available(self):
                return True
            
            def chat_once(self, user, system="", **kwargs):
                if "bewerte" in system.lower():
                    # Evaluation request
                    return '{"scores": {"correctness": 8, "relevance": 8, "completeness": 7}, "confidence": 0.8, "suggestions": []}'
                # Normal response
                return f"Mock answer for: {user}"
        
        return MockLLM()
    
    @pytest.fixture
    def mock_tools(self):
        """Mock tools"""
        return {
            "calc": lambda q: "8" if "5+3" in q else "0",
            "memory": lambda q: f"Info about {q}",
            "web": lambda q: f"Web: {q}"
        }
    
    def test_pipeline_with_learning(self, mock_llm, mock_tools, tmp_path):
        """Test pipeline recording to learning hub"""
        # Create learning hub
        hub = LearningHub(storage_path=str(tmp_path))
        
        # Create pipeline
        pipeline = ResponsePipeline(
            llm_backend=mock_llm,
            tools=mock_tools,
            enable_reflection=True
        )
        
        # Inject learning hub (normally done automatically)
        pipeline.learning_hub = hub
        
        # Generate response
        response = pipeline.generate("Was ist 5+3?")
        
        # Check that interaction was recorded
        stats = hub.get_statistics()
        assert stats["total_interactions"] > 0
    
    def test_decision_engine_with_tools(self, mock_tools):
        """Test decision engine executing with real tools"""
        engine = DecisionEngine(tools=mock_tools)
        
        # Create and execute plan
        plan = engine.analyze_goal("Was ist 5+3?")
        result = engine.execute_plan(plan)
        
        assert result["ok"]
        assert plan.is_complete()
        assert len(result["results"]) > 0
    
    def test_meta_mind_with_learning_hub(self, tmp_path):
        """Test meta-mind reading from learning hub"""
        # Create learning hub with some data
        hub = LearningHub(storage_path=str(tmp_path))
        hub.record_interaction("Test", "Answer", 0.85, ["calc"], 0)
        hub.record_tool_use("calc", True, 100)
        
        # Create meta-mind
        meta = MetaMind()
        
        # Evaluate (should read from hub)
        state = meta.evaluate_system_state()
        
        # Should have captured data
        assert state.total_interactions > 0
    
    def test_full_pipeline_flow(self, mock_llm, mock_tools, tmp_path):
        """Test complete flow: Question → Pipeline → Reflection → Learning"""
        # Setup
        hub = LearningHub(storage_path=str(tmp_path))
        reflector = ResponseReflector(mock_llm, quality_threshold=0.7)
        pipeline = ResponsePipeline(
            llm_backend=mock_llm,
            reflector=reflector,
            tools=mock_tools,
            enable_reflection=True
        )
        pipeline.learning_hub = hub
        
        # Execute
        response = pipeline.generate("Was ist 5+3?")
        
        # Verify flow
        assert response.ok
        assert response.reply is not None
        assert response.evaluation is not None  # Reflection happened
        
        # Check learning recorded
        stats = hub.get_statistics()
        assert stats["total_interactions"] >= 1
        
        # Check tool tracking
        if "calc" in stats["tools"]:
            assert stats["tools"]["calc"]["uses"] > 0
    
    def test_autonomous_improvement_cycle(self, tmp_path):
        """Test autonomous improvement detection and triggering"""
        # Setup system with poor performance
        hub = LearningHub(storage_path=str(tmp_path))
        
        # Record poor interactions
        for i in range(5):
            hub.record_interaction(
                f"Question {i}",
                f"Answer {i}",
                quality_score=0.4,  # Poor quality
                tools_used=["calc"],
                retry_count=2  # Many retries
            )
            hub.record_tool_use("calc", success=False, response_time_ms=5000)
        
        # Meta-mind should detect issues
        meta = MetaMind()
        state = meta.evaluate_system_state()
        
        # Should have warnings due to poor quality
        plans = meta.plan_improvements()
        
        # Should have improvement suggestions
        assert len(plans) > 0
        
        # Plans should be prioritized
        assert plans[0].priority <= plans[-1].priority


class TestEndToEnd:
    """End-to-end scenarios"""
    
    def test_simple_question_scenario(self, tmp_path):
        """Test complete scenario: user asks simple question"""
        from netapi.core import llm_mock
        
        # Mock tools
        tools = {
            "calc": lambda q: "8",
            "memory": lambda q: "Python is a programming language",
            "web": lambda q: "Web results"
        }
        
        # Create pipeline
        pipeline = ResponsePipeline(
            llm_backend=llm_mock,
            tools=tools,
            enable_reflection=True
        )
        
        # User asks question
        response = pipeline.generate("Was ist 5+3?")
        
        # Should get answer
        assert response.ok
        assert response.reply
        assert "8" in response.reply or "Mock" in response.reply  # Mock LLM response
    
    def test_complex_question_scenario(self, tmp_path):
        """Test complex question requiring multiple steps"""
        from netapi.core import llm_mock
        
        tools = {
            "calc": lambda q: "Result",
            "memory": lambda q: f"Info: {q}",
            "web": lambda q: f"Web: {q}",
            "synthesize": lambda q: f"Synthesis: {q}"
        }
        
        # Create decision engine
        engine = DecisionEngine(tools=tools, llm_backend=llm_mock)
        
        # Complex question
        plan = engine.analyze_goal("Vergleiche Python und JavaScript")
        
        # Should create multi-step plan
        assert len(plan.tasks) >= 2
        
        # Execute
        result = engine.execute_plan(plan)
        assert result["ok"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
