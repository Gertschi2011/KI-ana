"""
Unit tests for Decision Engine
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from netapi.autonomy.decision_engine import (
    DecisionEngine,
    ExecutionPlan,
    Task,
    TaskType,
    Priority
)


class TestDecisionEngine:
    """Test suite for DecisionEngine"""
    
    @pytest.fixture
    def mock_tools(self):
        """Create mock tools for testing"""
        def mock_calc(q: str) -> str:
            if "5+3" in q:
                return "8"
            if "10*2" in q:
                return "20"
            return "0"
        
        def mock_memory(q: str) -> str:
            return f"Info about {q}"
        
        def mock_web(q: str) -> str:
            return f"Web results for {q}"
        
        def mock_synthesize(q: str) -> str:
            return f"Synthesized: {q}"
        
        return {
            "calc": mock_calc,
            "memory": mock_memory,
            "web": mock_web,
            "synthesize": mock_synthesize
        }
    
    @pytest.fixture
    def engine(self, mock_tools):
        """Create DecisionEngine instance"""
        return DecisionEngine(tools=mock_tools)
    
    def test_engine_initialization(self, engine):
        """Test that engine initializes correctly"""
        assert engine.tools is not None
        assert engine._task_counter == 0
    
    def test_simple_calculation_plan(self, engine):
        """Test planning for simple calculation"""
        plan = engine.analyze_goal("Was ist 5+3?")
        
        assert len(plan.tasks) == 1
        assert plan.tasks[0].type == TaskType.CALCULATION
        assert plan.tasks[0].tool == "calc"
    
    def test_comparison_plan(self, engine):
        """Test planning for comparison task"""
        plan = engine.analyze_goal("Vergleiche Python und JavaScript")
        
        # Should create: gather info for both + synthesize
        assert len(plan.tasks) >= 2
        
        # Check for synthesis task with dependencies
        synthesis_tasks = [t for t in plan.tasks if t.type == TaskType.SYNTHESIS]
        assert len(synthesis_tasks) > 0
        assert len(synthesis_tasks[0].dependencies) > 0
    
    def test_multi_part_question_plan(self, engine):
        """Test planning for multi-part question"""
        plan = engine.analyze_goal("Was ist Python? Und was ist JavaScript?")
        
        # Should split into multiple tasks
        assert len(plan.tasks) >= 2
    
    def test_execute_simple_plan(self, engine):
        """Test executing a simple plan"""
        plan = engine.analyze_goal("Was ist 5+3?")
        result = engine.execute_plan(plan)
        
        assert result["ok"]
        assert plan.is_complete()
        assert len(result["results"]) > 0
    
    def test_execute_plan_with_dependencies(self, engine):
        """Test executing plan with task dependencies"""
        plan = engine.analyze_goal("Vergleiche Python und JavaScript")
        result = engine.execute_plan(plan)
        
        assert result["ok"]
        assert plan.is_complete()
        
        # Check that all tasks completed or failed
        for task in plan.tasks:
            assert task.status in ("completed", "failed")
    
    def test_plan_ready_tasks(self, mock_tools):
        """Test getting ready-to-execute tasks"""
        engine = DecisionEngine(mock_tools)
        
        # Create plan with dependencies
        task1 = Task(
            id="task_1",
            type=TaskType.INFORMATION_GATHERING,
            description="First",
            tool="memory",
            input="Python"
        )
        
        task2 = Task(
            id="task_2",
            type=TaskType.INFORMATION_GATHERING,
            description="Second",
            tool="memory",
            input="JavaScript",
            dependencies=["task_1"]  # Depends on task1
        )
        
        plan = ExecutionPlan(goal="Test", tasks=[task1, task2])
        
        # Initially, only task1 should be ready
        ready = plan.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "task_1"
        
        # Complete task1
        task1.status = "completed"
        
        # Now task2 should be ready
        ready = plan.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "task_2"


class TestExecutionPlan:
    """Test ExecutionPlan class"""
    
    def test_plan_creation(self):
        """Test creating execution plan"""
        plan = ExecutionPlan(
            goal="Test goal",
            tasks=[
                Task("1", TaskType.CALCULATION, "Calc", "calc", "5+3")
            ]
        )
        
        assert plan.goal == "Test goal"
        assert len(plan.tasks) == 1
    
    def test_is_complete(self):
        """Test plan completion detection"""
        task1 = Task("1", TaskType.CALCULATION, "T1", "calc", "test")
        task2 = Task("2", TaskType.MEMORY_SEARCH, "T2", "memory", "test")
        
        plan = ExecutionPlan(goal="Test", tasks=[task1, task2])
        
        # Initially not complete
        assert not plan.is_complete()
        
        # Complete one task
        task1.status = "completed"
        assert not plan.is_complete()
        
        # Complete both
        task2.status = "completed"
        assert plan.is_complete()
    
    def test_get_results(self):
        """Test getting results from completed tasks"""
        task1 = Task("1", TaskType.CALCULATION, "T1", "calc", "5+3")
        task1.status = "completed"
        task1.result = "8"
        
        task2 = Task("2", TaskType.MEMORY_SEARCH, "T2", "memory", "test")
        task2.status = "pending"
        
        plan = ExecutionPlan(goal="Test", tasks=[task1, task2])
        results = plan.get_results()
        
        # Should only include completed tasks
        assert "1" in results
        assert "2" not in results
        assert results["1"] == "8"
    
    def test_to_dict(self):
        """Test serialization to dict"""
        task = Task("1", TaskType.CALCULATION, "Test", "calc", "5+3")
        task.status = "completed"
        
        plan = ExecutionPlan(goal="Test goal", tasks=[task])
        
        d = plan.to_dict()
        
        assert d["goal"] == "Test goal"
        assert d["total_tasks"] == 1
        assert d["completed"] == 1
        assert d["failed"] == 0


class TestTask:
    """Test Task dataclass"""
    
    def test_task_creation(self):
        """Test creating a task"""
        task = Task(
            id="task_1",
            type=TaskType.CALCULATION,
            description="Calculate something",
            tool="calc",
            input="5+3",
            priority=Priority.HIGH
        )
        
        assert task.id == "task_1"
        assert task.type == TaskType.CALCULATION
        assert task.priority == Priority.HIGH
        assert task.status == "pending"
    
    def test_task_duration(self):
        """Test duration calculation"""
        task = Task("1", TaskType.CALCULATION, "Test", "calc", "test")
        
        # No duration yet
        assert task.duration_ms() == 0
        
        # Set times
        task.start_time = 1.0
        task.end_time = 1.5
        
        assert task.duration_ms() == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
