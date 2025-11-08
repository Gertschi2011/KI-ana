"""
Autonomous Execution - Auto-execute Learning Goals

Automatically executes identified learning goals:
- Research topics autonomously
- Gather information from web
- Create knowledge blocks
- Track progress
"""
from __future__ import annotations
import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class ExecutionResult:
    """Result of autonomous execution"""
    goal_id: str
    success: bool
    blocks_created: int
    sources_used: List[str]
    duration_seconds: float
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "success": self.success,
            "blocks_created": self.blocks_created,
            "sources_used": self.sources_used,
            "duration_seconds": self.duration_seconds,
            "error": self.error
        }


class AutonomousExecutor:
    """
    Executes learning goals autonomously.
    
    Takes goals from AutonomousGoalEngine and executes them:
    1. Research topic using web search
    2. Gather and parse information
    3. Create knowledge blocks
    4. Mark goal as completed
    
    Usage:
        executor = AutonomousExecutor()
        result = await executor.execute_goal(goal)
    """
    
    def __init__(self):
        self.runtime_dir = Path.home() / "ki_ana" / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.execution_log = self.runtime_dir / "execution_log.json"
        self.max_concurrent = 2  # Max goals to execute in parallel
    
    async def execute_goal(self, goal) -> ExecutionResult:
        """
        Execute a single learning goal autonomously.
        
        Args:
            goal: LearningGoal object
            
        Returns:
            ExecutionResult
        """
        start_time = time.time()
        blocks_created = 0
        sources_used = []
        
        try:
            # Mark goal as in progress
            goal.status = "in_progress"
            goal.started_at = time.time()
            
            # Step 1: Research topic
            print(f"🔍 Researching: {goal.topic}")
            research_results = await self._research_topic(goal)
            
            if not research_results:
                raise Exception("No research results found")
            
            # Step 2: Create knowledge blocks
            print(f"📝 Creating knowledge blocks for: {goal.topic}")
            for result in research_results:
                try:
                    block_created = await self._create_knowledge_block(goal, result)
                    if block_created:
                        blocks_created += 1
                        if result.get("url"):
                            sources_used.append(result["url"])
                except Exception as e:
                    print(f"  ⚠️  Failed to create block: {e}")
            
            # Step 3: Update goal
            goal.status = "completed"
            goal.completed_at = time.time()
            goal.blocks_created = blocks_created
            goal.research_attempts += 1
            goal.success_rate = blocks_created / len(research_results) if research_results else 0.0
            
            duration = time.time() - start_time
            
            print(f"✅ Completed: {goal.topic} ({blocks_created} blocks, {duration:.1f}s)")
            
            return ExecutionResult(
                goal_id=goal.id,
                success=True,
                blocks_created=blocks_created,
                sources_used=sources_used,
                duration_seconds=duration
            )
            
        except Exception as e:
            goal.status = "failed"
            duration = time.time() - start_time
            
            print(f"❌ Failed: {goal.topic} - {e}")
            
            return ExecutionResult(
                goal_id=goal.id,
                success=False,
                blocks_created=blocks_created,
                sources_used=sources_used,
                duration_seconds=duration,
                error=str(e)
            )
    
    async def _research_topic(self, goal) -> List[Dict[str, Any]]:
        """Research a topic using available sources"""
        results = []
        
        try:
            # Try web search first
            from ...web_qa import web_search
            
            for keyword in goal.keywords[:3]:  # Use top 3 keywords
                try:
                    search_results = await web_search(keyword, top_k=3)
                    if search_results:
                        results.extend(search_results)
                except Exception as e:
                    print(f"  ⚠️  Web search failed for '{keyword}': {e}")
            
            # Deduplicate by URL
            seen_urls = set()
            unique_results = []
            for r in results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_results.append(r)
            
            return unique_results[:5]  # Limit to top 5
            
        except Exception as e:
            print(f"  ⚠️  Research failed: {e}")
            return []
    
    async def _create_knowledge_block(self, goal, research_result: Dict[str, Any]) -> bool:
        """Create a knowledge block from research result"""
        try:
            from ... import memory_store
            
            title = research_result.get("title", goal.topic)
            content = research_result.get("snippet", research_result.get("text", ""))
            url = research_result.get("url", "")
            
            if not content:
                return False
            
            # Create block
            memory_store.add_block(
                title=title,
                content=content,
                tags=["autonomous_learning", goal.topic.lower().replace(" ", "_")],
                url=url,
                meta={
                    "goal_id": goal.id,
                    "learned_at": int(time.time()),
                    "autonomous": True
                }
            )
            
            return True
            
        except Exception as e:
            print(f"  ⚠️  Block creation failed: {e}")
            return False
    
    async def execute_batch(self, goals: List) -> List[ExecutionResult]:
        """
        Execute multiple goals in parallel (limited concurrency).
        
        Args:
            goals: List of LearningGoal objects
            
        Returns:
            List of ExecutionResult
        """
        results = []
        
        # Execute in batches
        for i in range(0, len(goals), self.max_concurrent):
            batch = goals[i:i + self.max_concurrent]
            
            tasks = [self.execute_goal(goal) for goal in batch]
            batch_results = await asyncio.gather(*tasks)
            
            results.extend(batch_results)
        
        return results
    
    async def auto_execute_top_goals(self, n: int = 3) -> List[ExecutionResult]:
        """
        Automatically execute top N pending learning goals.
        
        Args:
            n: Number of goals to execute
            
        Returns:
            List of ExecutionResult
        """
        try:
            from ...system.autonomous_goals import get_autonomous_goal_engine
            engine = get_autonomous_goal_engine()
            
            # Get top pending goals
            top_goals = engine.get_top_goals(n)
            
            if not top_goals:
                print("ℹ️  No pending learning goals")
                return []
            
            print(f"\n🤖 Auto-executing {len(top_goals)} learning goal(s)...")
            
            # Execute
            results = await self.execute_batch(top_goals)
            
            # Save engine state
            engine._save_state()
            
            # Log execution
            self._log_execution(results)
            
            return results
            
        except Exception as e:
            print(f"❌ Auto-execution failed: {e}")
            return []
    
    def _log_execution(self, results: List[ExecutionResult]):
        """Log execution results"""
        try:
            log_entry = {
                "timestamp": time.time(),
                "results": [r.to_dict() for r in results],
                "total_goals": len(results),
                "successful": sum(1 for r in results if r.success),
                "total_blocks": sum(r.blocks_created for r in results)
            }
            
            # Append to log
            logs = []
            if self.execution_log.exists():
                try:
                    logs = json.loads(self.execution_log.read_text())
                except Exception:
                    logs = []
            
            logs.append(log_entry)
            
            # Keep last 100 executions
            if len(logs) > 100:
                logs = logs[-100:]
            
            self.execution_log.write_text(json.dumps(logs, indent=2))
            
        except Exception as e:
            print(f"⚠️  Failed to log execution: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics"""
        try:
            if not self.execution_log.exists():
                return {"total_executions": 0}
            
            logs = json.loads(self.execution_log.read_text())
            
            total_goals = sum(log["total_goals"] for log in logs)
            successful = sum(log["successful"] for log in logs)
            total_blocks = sum(log["total_blocks"] for log in logs)
            
            return {
                "total_executions": len(logs),
                "total_goals": total_goals,
                "successful_goals": successful,
                "success_rate": successful / total_goals if total_goals > 0 else 0.0,
                "total_blocks_created": total_blocks,
                "recent_executions": logs[-5:] if logs else []
            }
            
        except Exception:
            return {"total_executions": 0}


# Global instance
_autonomous_executor_instance: Optional[AutonomousExecutor] = None


def get_autonomous_executor() -> AutonomousExecutor:
    """Get or create global AutonomousExecutor instance"""
    global _autonomous_executor_instance
    if _autonomous_executor_instance is None:
        _autonomous_executor_instance = AutonomousExecutor()
    return _autonomous_executor_instance


if __name__ == "__main__":
    # Self-test
    print("=== Autonomous Executor Self-Test ===\n")
    
    async def test():
        executor = AutonomousExecutor()
        
        # Get statistics
        stats = executor.get_statistics()
        print(f"Total executions: {stats['total_executions']}")
        print(f"Total blocks created: {stats.get('total_blocks_created', 0)}")
        
        print("\n✅ Autonomous Executor functional!")
    
    asyncio.run(test())
