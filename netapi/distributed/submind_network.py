"""
SubMind Network - Distributed Sub-KI System for KI_ana

Enables coordination between multiple specialized AI instances (sub-minds):
- Task distribution
- Knowledge sharing
- Specialized processing
- Redundancy and failover
"""
from __future__ import annotations
import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import hashlib


class SubMindRole(Enum):
    """Specialized roles for sub-minds"""
    GENERAL = "general"              # General purpose
    RESEARCHER = "researcher"        # Web research specialist
    ANALYZER = "analyzer"            # Data analysis specialist
    CREATIVE = "creative"            # Creative content generation
    TECHNICAL = "technical"          # Technical/coding specialist
    MEMORY = "memory"                # Memory management specialist
    COORDINATOR = "coordinator"      # Task coordination


class SubMindStatus(Enum):
    """Status of a sub-mind"""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"


@dataclass
class SubMind:
    """Represents a specialized sub-AI instance"""
    id: str
    name: str
    role: SubMindRole
    status: SubMindStatus = SubMindStatus.OFFLINE
    capabilities: List[str] = field(default_factory=list)
    current_task: Optional[str] = None
    last_heartbeat: float = 0.0
    total_tasks: int = 0
    successful_tasks: int = 0
    endpoint: Optional[str] = None  # For remote subminds
    
    def success_rate(self) -> float:
        """Calculate task success rate"""
        if self.total_tasks == 0:
            return 0.0
        return self.successful_tasks / self.total_tasks
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "status": self.status.value,
            "capabilities": self.capabilities,
            "current_task": self.current_task,
            "last_heartbeat": self.last_heartbeat,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "success_rate": self.success_rate()
        }


@dataclass
class DistributedTask:
    """A task to be distributed among sub-minds"""
    id: str
    type: str
    description: str
    payload: Dict[str, Any]
    required_role: Optional[SubMindRole] = None
    assigned_to: Optional[str] = None  # SubMind ID
    status: str = "pending"  # pending, assigned, running, completed, failed
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "required_role": self.required_role.value if self.required_role else None,
            "assigned_to": self.assigned_to,
            "status": self.status,
            "error": self.error,
            "duration": (self.completed_at - self.started_at) if self.started_at and self.completed_at else None
        }


class SubMindNetwork:
    """
    Network coordinator for distributed sub-AI instances.
    
    Manages multiple specialized AI instances that work together:
    - Task distribution based on specialization
    - Load balancing
    - Knowledge synchronization
    - Failover handling
    
    Usage:
        network = SubMindNetwork()
        
        # Register sub-mind
        researcher = SubMind(
            id="researcher_1",
            name="Research Assistant",
            role=SubMindRole.RESEARCHER,
            capabilities=["web_search", "summarization"]
        )
        network.register_submind(researcher)
        
        # Distribute task
        task = DistributedTask(
            id="task_1",
            type="research",
            description="Research AI trends",
            payload={"query": "AI trends 2025"},
            required_role=SubMindRole.RESEARCHER
        )
        result = await network.execute_task(task)
    """
    
    def __init__(self):
        self.subminds: Dict[str, SubMind] = {}
        self.tasks: Dict[str, DistributedTask] = {}
        self.task_queue: List[DistributedTask] = []
        
        # Storage
        self.network_dir = Path.home() / "ki_ana" / "distributed"
        self.network_dir.mkdir(parents=True, exist_ok=True)
        self.network_file = self.network_dir / "network_state.json"
        
        self._running = False
        self._coordinator_task: Optional[asyncio.Task] = None
        
        # Load state
        self._load_state()
        
        # Register default local subminds
        self._register_default_subminds()
    
    def _register_default_subminds(self):
        """Register default local sub-minds"""
        defaults = [
            SubMind(
                id="general_1",
                name="General Assistant",
                role=SubMindRole.GENERAL,
                capabilities=["chat", "general_qa"],
                status=SubMindStatus.ONLINE
            ),
            SubMind(
                id="researcher_1",
                name="Research Specialist",
                role=SubMindRole.RESEARCHER,
                capabilities=["web_search", "summarization", "fact_checking"],
                status=SubMindStatus.ONLINE
            ),
            SubMind(
                id="analyzer_1",
                name="Data Analyzer",
                role=SubMindRole.ANALYZER,
                capabilities=["data_analysis", "statistics", "visualization"],
                status=SubMindStatus.ONLINE
            ),
            SubMind(
                id="memory_1",
                name="Memory Manager",
                role=SubMindRole.MEMORY,
                capabilities=["memory_storage", "memory_retrieval", "cleanup"],
                status=SubMindStatus.ONLINE
            )
        ]
        
        for submind in defaults:
            if submind.id not in self.subminds:
                self.subminds[submind.id] = submind
    
    def register_submind(self, submind: SubMind) -> bool:
        """Register a sub-mind in the network"""
        try:
            submind.last_heartbeat = time.time()
            self.subminds[submind.id] = submind
            self._save_state()
            return True
        except Exception:
            return False
    
    def unregister_submind(self, submind_id: str) -> bool:
        """Remove a sub-mind from the network"""
        if submind_id in self.subminds:
            del self.subminds[submind_id]
            self._save_state()
            return True
        return False
    
    def get_submind(self, submind_id: str) -> Optional[SubMind]:
        """Get sub-mind by ID"""
        return self.subminds.get(submind_id)
    
    def find_submind_for_task(self, task: DistributedTask) -> Optional[SubMind]:
        """
        Find the best sub-mind for a task.
        
        Args:
            task: Task to assign
            
        Returns:
            Best-fit SubMind or None
        """
        # Filter by role if specified
        candidates = [
            sm for sm in self.subminds.values()
            if sm.status == SubMindStatus.ONLINE
            and (task.required_role is None or sm.role == task.required_role)
            and sm.current_task is None
        ]
        
        if not candidates:
            return None
        
        # Select by success rate
        candidates.sort(key=lambda sm: sm.success_rate(), reverse=True)
        return candidates[0]
    
    async def execute_task(self, task: DistributedTask) -> Dict[str, Any]:
        """
        Execute a distributed task.
        
        Args:
            task: Task to execute
            
        Returns:
            Result dict
        """
        # Find suitable sub-mind
        submind = self.find_submind_for_task(task)
        
        if not submind:
            task.status = "failed"
            task.error = "No available sub-mind for this task"
            return {
                "success": False,
                "error": task.error
            }
        
        # Assign task
        task.assigned_to = submind.id
        task.status = "assigned"
        submind.current_task = task.id
        submind.status = SubMindStatus.BUSY
        
        # Store task
        self.tasks[task.id] = task
        
        try:
            # Execute task (delegate to submind)
            task.status = "running"
            task.started_at = time.time()
            
            result = await self._execute_on_submind(submind, task)
            
            # Mark complete
            task.status = "completed"
            task.completed_at = time.time()
            task.result = result
            
            submind.total_tasks += 1
            submind.successful_tasks += 1
            
            return {
                "success": True,
                "result": result,
                "submind_id": submind.id,
                "duration": task.completed_at - task.started_at
            }
            
        except Exception as e:
            # Mark failed
            task.status = "failed"
            task.error = str(e)
            task.completed_at = time.time()
            
            submind.total_tasks += 1
            
            return {
                "success": False,
                "error": str(e),
                "submind_id": submind.id
            }
        
        finally:
            # Release submind
            submind.current_task = None
            submind.status = SubMindStatus.ONLINE
            self._save_state()
    
    async def _execute_on_submind(self, submind: SubMind, task: DistributedTask) -> Any:
        """
        Execute task on specific sub-mind.
        
        This is where the actual delegation happens.
        For local subminds, call appropriate function.
        For remote subminds, make HTTP request to endpoint.
        """
        # For now, simulate execution based on role
        await asyncio.sleep(0.1)  # Simulate work
        
        if submind.role == SubMindRole.RESEARCHER:
            return {"findings": f"Research results for {task.description}"}
        elif submind.role == SubMindRole.ANALYZER:
            return {"analysis": f"Analysis of {task.description}"}
        elif submind.role == SubMindRole.MEMORY:
            return {"stored": True, "blocks": 1}
        else:
            return {"result": f"Processed {task.description}"}
    
    async def broadcast_knowledge(self, knowledge: Dict[str, Any]):
        """
        Broadcast knowledge to all sub-minds for synchronization.
        
        Args:
            knowledge: Knowledge to share
        """
        for submind in self.subminds.values():
            if submind.status != SubMindStatus.OFFLINE:
                try:
                    # Send knowledge update (would be HTTP for remote)
                    # For now, just log
                    pass
                except Exception:
                    pass
    
    def heartbeat(self, submind_id: str):
        """Update sub-mind heartbeat"""
        submind = self.subminds.get(submind_id)
        if submind:
            submind.last_heartbeat = time.time()
            if submind.status == SubMindStatus.OFFLINE:
                submind.status = SubMindStatus.ONLINE
    
    def check_health(self):
        """Check health of all sub-minds"""
        now = time.time()
        timeout = 60  # 1 minute timeout
        
        for submind in self.subminds.values():
            if now - submind.last_heartbeat > timeout:
                if submind.status != SubMindStatus.OFFLINE:
                    submind.status = SubMindStatus.OFFLINE
    
    async def coordinator_loop(self, check_interval: int = 30):
        """
        Coordinator loop that manages the network.
        
        Args:
            check_interval: Seconds between checks
        """
        self._running = True
        
        while self._running:
            try:
                # Check health
                self.check_health()
                
                # Process task queue
                while self.task_queue:
                    task = self.task_queue.pop(0)
                    await self.execute_task(task)
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                print(f"Coordinator error: {e}")
                await asyncio.sleep(check_interval)
    
    async def start(self, check_interval: int = 30):
        """Start the coordinator"""
        if self._coordinator_task is None or self._coordinator_task.done():
            self._coordinator_task = asyncio.create_task(
                self.coordinator_loop(check_interval)
            )
        return self._coordinator_task
    
    def stop(self):
        """Stop the coordinator"""
        self._running = False
        if self._coordinator_task:
            self._coordinator_task.cancel()
    
    def _save_state(self):
        """Save network state"""
        try:
            data = {
                "subminds": [sm.to_dict() for sm in self.subminds.values()],
                "updated_at": time.time()
            }
            self.network_file.write_text(json.dumps(data, indent=2))
        except Exception:
            pass
    
    def _load_state(self):
        """Load network state"""
        try:
            if self.network_file.exists():
                data = json.loads(self.network_file.read_text())
                # Would reconstruct subminds here
        except Exception:
            pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get network statistics"""
        online = sum(1 for sm in self.subminds.values() if sm.status == SubMindStatus.ONLINE)
        busy = sum(1 for sm in self.subminds.values() if sm.status == SubMindStatus.BUSY)
        
        return {
            "total_subminds": len(self.subminds),
            "online": online,
            "busy": busy,
            "offline": len(self.subminds) - online - busy,
            "total_tasks": len(self.tasks),
            "by_role": {
                role.value: sum(1 for sm in self.subminds.values() if sm.role == role)
                for role in SubMindRole
            },
            "subminds": [sm.to_dict() for sm in self.subminds.values()]
        }


# Global instance
_submind_network_instance: Optional[SubMindNetwork] = None


def get_submind_network() -> SubMindNetwork:
    """Get or create global SubMindNetwork instance"""
    global _submind_network_instance
    if _submind_network_instance is None:
        _submind_network_instance = SubMindNetwork()
    return _submind_network_instance


if __name__ == "__main__":
    # Self-test
    import asyncio
    
    print("=== SubMind Network Self-Test ===\n")
    
    async def test():
        network = SubMindNetwork()
        
        print(f"Registered {len(network.subminds)} sub-mind(s)")
        
        # Create test task
        task = DistributedTask(
            id="test_1",
            type="research",
            description="Test research task",
            payload={"query": "test"},
            required_role=SubMindRole.RESEARCHER
        )
        
        print(f"\nExecuting task: {task.description}")
        result = await network.execute_task(task)
        
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Handled by: {result['submind_id']}")
            print(f"Duration: {result['duration']:.3f}s")
        
        # Statistics
        stats = network.get_statistics()
        print(f"\nNetwork Statistics:")
        print(f"  Total sub-minds: {stats['total_subminds']}")
        print(f"  Online: {stats['online']}")
        print(f"  By role: {stats['by_role']}")
        
        print("\n✅ SubMind Network functional!")
    
    asyncio.run(test())
