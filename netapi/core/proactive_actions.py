"""
Proactive Actions - Autonomous Task Initiation for KI_ana

Enables the AI to:
- Initiate tasks without explicit user request
- Schedule periodic checks and updates
- Suggest improvements proactively
- Monitor for conditions that need attention
"""
from __future__ import annotations
import time
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json


class ActionPriority(Enum):
    """Priority levels for proactive actions"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    OPTIONAL = 5


class ActionStatus(Enum):
    """Status of proactive actions"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProactiveAction:
    """Represents a proactive action the AI can take"""
    id: str
    name: str
    description: str
    priority: ActionPriority
    condition: Callable[[], bool]  # Function that returns True if action should run
    action: Callable[[], Any]  # Function to execute
    interval_seconds: int = 3600  # How often to check (default: 1 hour)
    last_check: float = 0.0
    last_run: float = 0.0
    run_count: int = 0
    status: ActionStatus = ActionStatus.PENDING
    error: Optional[str] = None
    
    def should_run(self) -> bool:
        """Check if enough time has passed and condition is met"""
        now = time.time()
        if now - self.last_check < self.interval_seconds:
            return False
        
        self.last_check = now
        try:
            return self.condition()
        except Exception as e:
            self.error = str(e)
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority.value,
            "interval_seconds": self.interval_seconds,
            "last_run": self.last_run,
            "run_count": self.run_count,
            "status": self.status.value,
            "error": self.error
        }


class ProactiveEngine:
    """
    Engine for managing and executing proactive actions.
    
    The AI uses this to autonomously initiate tasks based on conditions.
    
    Usage:
        engine = ProactiveEngine()
        
        # Register action
        engine.register_action(
            "check_memory",
            "Check memory usage and cleanup if needed",
            condition=lambda: get_memory_usage() > 0.8,
            action=lambda: cleanup_memory(),
            priority=ActionPriority.HIGH,
            interval_seconds=3600
        )
        
        # Start monitoring
        await engine.start()
    """
    
    def __init__(self):
        self.actions: Dict[str, ProactiveAction] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.runtime_dir = Path.home() / "ki_ana" / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.actions_file = self.runtime_dir / "proactive_actions.json"
        
        # Register default actions
        self._register_default_actions()
    
    def register_action(
        self,
        action_id: str,
        name: str,
        description: str,
        condition: Callable[[], bool],
        action: Callable[[], Any],
        priority: ActionPriority = ActionPriority.MEDIUM,
        interval_seconds: int = 3600
    ) -> ProactiveAction:
        """Register a new proactive action"""
        pa = ProactiveAction(
            id=action_id,
            name=name,
            description=description,
            priority=priority,
            condition=condition,
            action=action,
            interval_seconds=interval_seconds
        )
        
        self.actions[action_id] = pa
        return pa
    
    def _register_default_actions(self):
        """Register built-in proactive actions"""
        
        # 1. Memory cleanup check
        self.register_action(
            "memory_cleanup_check",
            "Memory Cleanup Check",
            "Check if memory cleanup is needed",
            condition=self._should_cleanup_memory,
            action=self._trigger_memory_cleanup,
            priority=ActionPriority.MEDIUM,
            interval_seconds=86400  # Daily
        )
        
        # 2. Learning goals update
        self.register_action(
            "update_learning_goals",
            "Update Learning Goals",
            "Identify new knowledge gaps and set learning goals",
            condition=self._should_update_goals,
            action=self._update_learning_goals,
            priority=ActionPriority.MEDIUM,
            interval_seconds=604800  # Weekly
        )
        
        # 3. System health check
        self.register_action(
            "system_health_check",
            "System Health Check",
            "Check system health and trigger optimizations if needed",
            condition=self._should_check_health,
            action=self._check_system_health,
            priority=ActionPriority.HIGH,
            interval_seconds=3600  # Hourly
        )
        
        # 4. Knowledge base maintenance
        self.register_action(
            "kb_maintenance",
            "Knowledge Base Maintenance",
            "Reorganize and optimize knowledge base",
            condition=self._should_maintain_kb,
            action=self._maintain_knowledge_base,
            priority=ActionPriority.LOW,
            interval_seconds=604800  # Weekly
        )
        
        # 5. User engagement check
        self.register_action(
            "user_engagement",
            "User Engagement Check",
            "Check for inactive users and suggest re-engagement",
            condition=self._should_check_engagement,
            action=self._check_user_engagement,
            priority=ActionPriority.LOW,
            interval_seconds=86400  # Daily
        )
    
    # Condition functions
    def _should_cleanup_memory(self) -> bool:
        """Check if memory cleanup is needed"""
        try:
            from .time_awareness import get_time_awareness
            ta = get_time_awareness()
            # Run if not done in last 24 hours
            return ta.should_trigger_action("memory_cleanup", 86400)
        except Exception:
            return False
    
    def _should_update_goals(self) -> bool:
        """Check if learning goals should be updated"""
        try:
            from .time_awareness import get_time_awareness
            ta = get_time_awareness()
            # Run if not done in last 7 days
            return ta.should_trigger_action("update_goals", 604800)
        except Exception:
            return False
    
    def _should_check_health(self) -> bool:
        """Check if system health check is due"""
        try:
            from .time_awareness import get_time_awareness
            ta = get_time_awareness()
            # Run every hour
            return ta.should_trigger_action("health_check", 3600)
        except Exception:
            return True  # Always check if unsure
    
    def _should_maintain_kb(self) -> bool:
        """Check if KB maintenance is needed"""
        try:
            from ...db import total_blocks
            # Run if more than 1000 blocks
            return total_blocks() > 1000
        except Exception:
            return False
    
    def _should_check_engagement(self) -> bool:
        """Check if user engagement analysis is due"""
        try:
            from .time_awareness import get_time_awareness
            ta = get_time_awareness()
            # Run daily
            return ta.should_trigger_action("engagement_check", 86400)
        except Exception:
            return False
    
    # Action functions
    def _trigger_memory_cleanup(self):
        """Trigger memory cleanup"""
        try:
            from ..modules.chat.ai_consciousness import auto_cleanup_memories
            result = auto_cleanup_memories(max_age_days=30, min_confidence=0.2)
            
            from .time_awareness import get_time_awareness
            ta = get_time_awareness()
            ta.track_event("memory_cleanup", f"Deleted {result.get('deleted_blocks', 0)} blocks")
            
            return result
        except Exception as e:
            return {"error": str(e)}
    
    def _update_learning_goals(self):
        """Update autonomous learning goals"""
        try:
            from ...system.autonomous_goals import get_autonomous_goal_engine
            engine = get_autonomous_goal_engine()
            
            # Identify gaps
            gaps = engine.identify_knowledge_gaps()
            
            # Prioritize and create goals
            goals = engine.prioritize_goals(gaps)
            
            from .time_awareness import get_time_awareness
            ta = get_time_awareness()
            ta.track_event("update_goals", f"Created {len(goals)} new learning goals")
            
            return {"gaps": len(gaps), "goals": len(goals)}
        except Exception as e:
            return {"error": str(e)}
    
    def _check_system_health(self):
        """Check system health"""
        try:
            from .meta_mind import get_meta_mind
            meta = get_meta_mind()
            
            state = meta.evaluate_system_state()
            
            # Trigger optimization if degraded
            if state.health_status.value in ["degraded", "critical"]:
                meta.trigger_optimization()
            
            from .time_awareness import get_time_awareness
            ta = get_time_awareness()
            ta.track_event("health_check", f"Status: {state.health_status.value}")
            
            return state.to_dict()
        except Exception as e:
            return {"error": str(e)}
    
    def _maintain_knowledge_base(self):
        """Maintain knowledge base"""
        try:
            # Placeholder for KB maintenance logic
            # Could include: deduplication, indexing, compression
            
            from .time_awareness import get_time_awareness
            ta = get_time_awareness()
            ta.track_event("kb_maintenance", "KB maintenance completed")
            
            return {"status": "completed"}
        except Exception as e:
            return {"error": str(e)}
    
    def _check_user_engagement(self):
        """Check user engagement"""
        try:
            # Placeholder for engagement analysis
            # Could include: inactive user detection, suggestion generation
            
            from .time_awareness import get_time_awareness
            ta = get_time_awareness()
            ta.track_event("engagement_check", "Engagement check completed")
            
            return {"status": "completed"}
        except Exception as e:
            return {"error": str(e)}
    
    async def execute_action(self, action: ProactiveAction) -> Dict[str, Any]:
        """Execute a single action"""
        action.status = ActionStatus.RUNNING
        start_time = time.time()
        
        try:
            # Run action
            result = action.action()
            
            action.status = ActionStatus.COMPLETED
            action.last_run = time.time()
            action.run_count += 1
            action.error = None
            
            return {
                "success": True,
                "action_id": action.id,
                "duration_ms": int((time.time() - start_time) * 1000),
                "result": result
            }
            
        except Exception as e:
            action.status = ActionStatus.FAILED
            action.error = str(e)
            
            return {
                "success": False,
                "action_id": action.id,
                "error": str(e)
            }
    
    async def check_and_execute(self):
        """Check all actions and execute if conditions are met"""
        results = []
        
        for action in sorted(self.actions.values(), key=lambda a: a.priority.value):
            if action.should_run():
                result = await self.execute_action(action)
                results.append(result)
        
        return results
    
    async def run_loop(self, check_interval: int = 300):
        """
        Main loop that checks and executes actions periodically.
        
        Args:
            check_interval: Seconds between checks (default: 5 minutes)
        """
        self._running = True
        
        print("🤖 Proactive Engine started")
        
        while self._running:
            try:
                results = await self.check_and_execute()
                
                if results:
                    print(f"✅ Executed {len(results)} proactive action(s)")
                    for r in results:
                        if r.get("success"):
                            print(f"  ✓ {r['action_id']}: {r.get('duration_ms')}ms")
                        else:
                            print(f"  ✗ {r['action_id']}: {r.get('error')}")
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                print(f"❌ Proactive engine error: {e}")
                await asyncio.sleep(check_interval)
    
    async def start(self, check_interval: int = 300):
        """Start the proactive engine"""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run_loop(check_interval))
        return self._task
    
    def stop(self):
        """Stop the proactive engine"""
        self._running = False
        if self._task:
            self._task.cancel()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get proactive engine statistics"""
        return {
            "total_actions": len(self.actions),
            "by_priority": {
                priority.name: len([a for a in self.actions.values() if a.priority == priority])
                for priority in ActionPriority
            },
            "by_status": {
                status.name: len([a for a in self.actions.values() if a.status == status])
                for status in ActionStatus
            },
            "actions": [a.to_dict() for a in self.actions.values()]
        }


# Global instance
_proactive_engine_instance: Optional[ProactiveEngine] = None


def get_proactive_engine() -> ProactiveEngine:
    """Get or create global ProactiveEngine instance"""
    global _proactive_engine_instance
    if _proactive_engine_instance is None:
        _proactive_engine_instance = ProactiveEngine()
    return _proactive_engine_instance


if __name__ == "__main__":
    # Self-test
    print("=== Proactive Engine Self-Test ===\n")
    
    engine = ProactiveEngine()
    
    # Test action registration
    def test_condition():
        return True
    
    def test_action():
        return {"message": "Test action executed"}
    
    engine.register_action(
        "test_action",
        "Test Action",
        "A test proactive action",
        condition=test_condition,
        action=test_action,
        priority=ActionPriority.HIGH,
        interval_seconds=1
    )
    
    print(f"Registered actions: {len(engine.actions)}")
    
    # Test execution
    async def test_run():
        results = await engine.check_and_execute()
        print(f"\nExecuted {len(results)} action(s)")
        for r in results:
            print(f"  {r['action_id']}: {'✓' if r['success'] else '✗'}")
    
    asyncio.run(test_run())
    
    print("\n✅ Proactive Engine functional!")
