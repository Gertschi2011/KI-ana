"""
Decision Engine - Autonomous Decision Making for KI_ana

Implements intelligent multi-step planning and decision-making:
- Break complex questions into sub-tasks
- Plan optimal tool execution order
- Adapt on failure
- Parallel execution when possible

Part of Phase 3: Autonomie
"""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class TaskType(Enum):
    """Types of tasks the engine can handle"""
    INFORMATION_GATHERING = "info"
    CALCULATION = "calc"
    MEMORY_SEARCH = "memory"
    WEB_RESEARCH = "web"
    COMPARISON = "compare"
    SYNTHESIS = "synthesize"
    VERIFICATION = "verify"


class Priority(Enum):
    """Task priority levels"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class Task:
    """A single task in the execution plan"""
    id: str
    type: TaskType
    description: str
    tool: str
    input: str
    priority: Priority = Priority.MEDIUM
    dependencies: List[str] = field(default_factory=list)  # Task IDs this depends on
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    def duration_ms(self) -> int:
        """Get task duration in milliseconds"""
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time) * 1000)
        return 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "description": self.description,
            "tool": self.tool,
            "priority": self.priority.value,
            "status": self.status,
            "duration_ms": self.duration_ms(),
            "has_result": self.result is not None,
            "error": self.error
        }


@dataclass
class ExecutionPlan:
    """Complete execution plan for a goal"""
    goal: str
    tasks: List[Task]
    created_at: float = field(default_factory=time.time)
    total_estimated_time_ms: int = 0
    
    def get_ready_tasks(self) -> List[Task]:
        """Get tasks that are ready to execute (dependencies met)"""
        ready = []
        completed_ids = {t.id for t in self.tasks if t.status == "completed"}
        
        for task in self.tasks:
            if task.status != "pending":
                continue
            
            # Check if all dependencies are completed
            deps_met = all(dep_id in completed_ids for dep_id in task.dependencies)
            if deps_met:
                ready.append(task)
        
        # Sort by priority
        ready.sort(key=lambda t: t.priority.value)
        return ready
    
    def is_complete(self) -> bool:
        """Check if all tasks are completed or failed"""
        return all(t.status in ("completed", "failed") for t in self.tasks)
    
    def get_results(self) -> Dict[str, Any]:
        """Get results from all completed tasks"""
        return {
            task.id: task.result
            for task in self.tasks
            if task.status == "completed" and task.result is not None
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "tasks": [t.to_dict() for t in self.tasks],
            "total_tasks": len(self.tasks),
            "completed": sum(1 for t in self.tasks if t.status == "completed"),
            "failed": sum(1 for t in self.tasks if t.status == "failed"),
            "is_complete": self.is_complete()
        }


class DecisionEngine:
    """
    Autonomous decision-making engine.
    
    Analyzes goals, creates execution plans, and orchestrates tool usage.
    
    Usage:
        engine = DecisionEngine(tools)
        plan = engine.analyze_goal("Compare Python and JavaScript")
        result = engine.execute_plan(plan)
    """
    
    def __init__(self, tools: Optional[Dict[str, Any]] = None, llm_backend=None):
        """
        Args:
            tools: Available tools {name: callable}
            llm_backend: LLM for plan generation (optional, uses heuristics if None)
        """
        self.tools = tools or {}
        self.llm = llm_backend
        self._task_counter = 0
    
    def analyze_goal(self, goal: str) -> ExecutionPlan:
        """
        Analyze a goal and create execution plan.
        
        Args:
            goal: User's goal/question
            
        Returns:
            ExecutionPlan with tasks to execute
        """
        # Use LLM for sophisticated planning if available
        if self.llm and hasattr(self.llm, 'available') and self.llm.available():
            return self._llm_based_planning(goal)
        
        # Fallback: Heuristic planning
        return self._heuristic_planning(goal)
    
    def execute_plan(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """
        Execute a plan and return results.
        
        Args:
            plan: ExecutionPlan to execute
            
        Returns:
            Dict with results and metadata
        """
        start_time = time.time()
        execution_trace = []
        
        while not plan.is_complete():
            # Get tasks ready to execute
            ready_tasks = plan.get_ready_tasks()
            
            if not ready_tasks:
                # No ready tasks but plan not complete = deadlock
                # Mark remaining tasks as failed
                for task in plan.tasks:
                    if task.status == "pending":
                        task.status = "failed"
                        task.error = "Dependency deadlock"
                break
            
            # Execute ready tasks (could be parallelized in future)
            for task in ready_tasks:
                self._execute_task(task, plan)
                execution_trace.append(task.to_dict())
        
        end_time = time.time()
        
        return {
            "ok": True,
            "plan": plan.to_dict(),
            "results": plan.get_results(),
            "trace": execution_trace,
            "total_time_ms": int((end_time - start_time) * 1000)
        }
    
    def _execute_task(self, task: Task, plan: ExecutionPlan):
        """Execute a single task"""
        task.status = "running"
        task.start_time = time.time()
        
        try:
            # Get tool
            tool_func = self.tools.get(task.tool)
            if not tool_func:
                raise Exception(f"Tool '{task.tool}' not found")
            
            # Build input from dependencies if needed
            task_input = task.input
            if task.dependencies:
                dep_results = [
                    t.result for t in plan.tasks
                    if t.id in task.dependencies and t.result is not None
                ]
                if dep_results:
                    # Combine dependency results with input
                    task_input = f"{task.input} | Context: {', '.join(str(r)[:100] for r in dep_results)}"
            
            # Execute tool
            result = tool_func(task_input)
            
            task.result = result
            task.status = "completed"
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
        
        finally:
            task.end_time = time.time()
    
    def _heuristic_planning(self, goal: str) -> ExecutionPlan:
        """
        Create plan using heuristics (when LLM unavailable).
        
        Analyzes goal text and creates appropriate task sequence.
        """
        goal_lower = goal.lower()
        tasks = []
        
        # Question type detection
        is_comparison = any(word in goal_lower for word in ["vergleich", "unterschied", "compare", "vs"])
        is_calculation = any(word in goal_lower for word in ["berechne", "rechne", "+", "-", "*", "/"])
        is_multi_part = goal.count("?") > 1 or goal.count(" und ") > 1
        
        # Build task list based on goal type
        
        if is_calculation:
            # Simple calculation
            task_id = self._next_task_id()
            tasks.append(Task(
                id=task_id,
                type=TaskType.CALCULATION,
                description="Berechnung durchführen",
                tool="calc",
                input=goal,
                priority=Priority.HIGH
            ))
        
        elif is_comparison:
            # Comparison requires multiple information gathering steps
            # Example: "Vergleiche Python und JavaScript"
            
            # Task 1: Research first item
            task1_id = self._next_task_id()
            first_item = self._extract_first_entity(goal)
            tasks.append(Task(
                id=task1_id,
                type=TaskType.INFORMATION_GATHERING,
                description=f"Informationen über {first_item} sammeln",
                tool="memory",
                input=first_item,
                priority=Priority.HIGH
            ))
            
            # Task 2: Research second item
            task2_id = self._next_task_id()
            second_item = self._extract_second_entity(goal)
            tasks.append(Task(
                id=task2_id,
                type=TaskType.INFORMATION_GATHERING,
                description=f"Informationen über {second_item} sammeln",
                tool="memory",
                input=second_item,
                priority=Priority.HIGH
            ))
            
            # Task 3: Synthesize comparison (depends on 1 & 2)
            task3_id = self._next_task_id()
            tasks.append(Task(
                id=task3_id,
                type=TaskType.SYNTHESIS,
                description="Vergleich erstellen",
                tool="synthesize",  # Special tool for synthesis
                input=goal,
                priority=Priority.MEDIUM,
                dependencies=[task1_id, task2_id]
            ))
        
        elif is_multi_part:
            # Multi-part question - break into sub-questions
            parts = self._split_multi_part_question(goal)
            
            for i, part in enumerate(parts):
                task_id = self._next_task_id()
                tasks.append(Task(
                    id=task_id,
                    type=TaskType.INFORMATION_GATHERING,
                    description=f"Teil-Frage {i+1} beantworten",
                    tool="memory",
                    input=part,
                    priority=Priority.HIGH if i == 0 else Priority.MEDIUM
                ))
        
        else:
            # Simple single-step question
            task_id = self._next_task_id()
            
            # Determine best tool
            if any(word in goal_lower for word in ["was ist", "wer ist", "wie", "warum"]):
                tool = "memory"
                task_type = TaskType.INFORMATION_GATHERING
            elif any(word in goal_lower for word in ["aktuell", "heute", "neueste"]):
                tool = "web"
                task_type = TaskType.WEB_RESEARCH
            else:
                tool = "memory"
                task_type = TaskType.INFORMATION_GATHERING
            
            tasks.append(Task(
                id=task_id,
                type=task_type,
                description="Frage beantworten",
                tool=tool,
                input=goal,
                priority=Priority.HIGH
            ))
        
        return ExecutionPlan(goal=goal, tasks=tasks)
    
    def _llm_based_planning(self, goal: str) -> ExecutionPlan:
        """
        Use LLM to generate sophisticated execution plan.
        
        Future: This will use LLM to break down complex goals intelligently.
        """
        # TODO: Implement when LLM available
        # For now, fallback to heuristic
        return self._heuristic_planning(goal)
    
    def _next_task_id(self) -> str:
        """Generate unique task ID"""
        self._task_counter += 1
        return f"task_{self._task_counter}"
    
    def _extract_first_entity(self, text: str) -> str:
        """Extract first entity from comparison text"""
        # Simple extraction - can be improved
        words = text.split()
        # Look for words after "vergleiche" or similar
        for i, word in enumerate(words):
            if word.lower() in ["vergleiche", "compare", "unterschied"]:
                if i + 1 < len(words):
                    return words[i + 1].strip(",")
        return text.split()[0] if words else text
    
    def _extract_second_entity(self, text: str) -> str:
        """Extract second entity from comparison text"""
        # Look for "und" or "and"
        text_lower = text.lower()
        for separator in [" und ", " and ", " vs ", " versus "]:
            if separator in text_lower:
                parts = text_lower.split(separator)
                if len(parts) >= 2:
                    # Get words around separator
                    second = parts[1].split()[0].strip(".,?!")
                    return second
        return text.split()[-1] if text.split() else text
    
    def _split_multi_part_question(self, text: str) -> List[str]:
        """Split multi-part question into sub-questions"""
        # Split on "und" or multiple "?"
        if text.count("?") > 1:
            parts = text.split("?")
            return [p.strip() + "?" for p in parts if p.strip()]
        elif " und " in text.lower():
            parts = text.split(" und ")
            return [p.strip() for p in parts if p.strip()]
        else:
            return [text]


# Global instance
_engine_instance: Optional[DecisionEngine] = None


def get_decision_engine(tools: Optional[Dict] = None, llm_backend=None) -> DecisionEngine:
    """Get or create global DecisionEngine instance"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = DecisionEngine(tools, llm_backend)
    return _engine_instance


if __name__ == "__main__":
    # Self-test
    print("=== Decision Engine Self-Test ===\n")
    
    # Mock tools
    def mock_calc(q: str) -> str:
        import re
        match = re.search(r'(\d+)\s*\+\s*(\d+)', q)
        if match:
            a, b = int(match.group(1)), int(match.group(2))
            return f"{a+b}"
        return "0"
    
    def mock_memory(q: str) -> str:
        return f"Information about: {q}"
    
    def mock_synthesize(q: str) -> str:
        return f"Synthesized answer for: {q}"
    
    tools = {
        "calc": mock_calc,
        "memory": mock_memory,
        "synthesize": mock_synthesize,
        "web": mock_memory
    }
    
    engine = DecisionEngine(tools)
    
    # Test 1: Simple calculation
    print("Test 1: Simple calculation")
    plan = engine.analyze_goal("Was ist 5+3?")
    print(f"Plan: {len(plan.tasks)} tasks")
    result = engine.execute_plan(plan)
    print(f"Result: {result['results']}\n")
    
    # Test 2: Comparison
    print("Test 2: Comparison")
    plan = engine.analyze_goal("Vergleiche Python und JavaScript")
    print(f"Plan: {len(plan.tasks)} tasks")
    for task in plan.tasks:
        print(f"  - {task.description} (depends on: {task.dependencies})")
    result = engine.execute_plan(plan)
    print(f"Completed: {result['plan']['completed']}/{result['plan']['total_tasks']}\n")
    
    # Test 3: Multi-part
    print("Test 3: Multi-part question")
    plan = engine.analyze_goal("Was ist Python? Und was ist JavaScript?")
    print(f"Plan: {len(plan.tasks)} tasks")
    result = engine.execute_plan(plan)
    print(f"Time: {result['total_time_ms']}ms")
