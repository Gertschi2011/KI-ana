"""
Workflow Engine

User-defined automation workflows.
"""

from typing import Dict, Any, List, Callable
from loguru import logger
import asyncio


class Workflow:
    """A workflow definition"""
    
    def __init__(self, name: str, trigger: str, actions: List[Dict]):
        self.name = name
        self.trigger = trigger
        self.actions = actions
        self.enabled = True


class WorkflowEngine:
    """
    Workflow Automation Engine
    
    Allows users to create custom workflows:
    - Trigger conditions
    - Automated actions
    - Scheduled tasks
    - Event-based automation
    """
    
    def __init__(self):
        self.workflows: List[Workflow] = []
        self.running = False
        
    def add_workflow(self, name: str, trigger: str, actions: List[Dict]):
        """Add new workflow"""
        workflow = Workflow(name, trigger, actions)
        self.workflows.append(workflow)
        logger.info(f"➕ Added workflow: {name}")
        
    def remove_workflow(self, name: str):
        """Remove workflow"""
        self.workflows = [w for w in self.workflows if w.name != name]
        logger.info(f"➖ Removed workflow: {name}")
    
    async def check_trigger(self, workflow: Workflow, context: Dict[str, Any]) -> bool:
        """Check if workflow trigger is met"""
        trigger = workflow.trigger
        
        # Time-based triggers (cron-like)
        if trigger.startswith("time:"):
            from datetime import datetime
            time_spec = trigger.split(":", 1)[1]
            
            # Simple hourly trigger: time:hourly
            if time_spec == "hourly":
                return datetime.now().minute == 0
            
            # Daily at specific time: time:daily:14:30
            if time_spec.startswith("daily:"):
                _, hour, minute = time_spec.split(":")
                now = datetime.now()
                return now.hour == int(hour) and now.minute == int(minute)
            
            return False
        
        # Event-based triggers
        if trigger.startswith("event:"):
            event_name = trigger.split(":", 1)[1]
            return context.get("event") == event_name
        
        # Condition-based triggers
        if trigger.startswith("if:"):
            condition = trigger.split(":", 1)[1]
            
            # CPU usage check: if:cpu>80
            if condition.startswith("cpu>"):
                import psutil
                threshold = int(condition.split(">")[1])
                return psutil.cpu_percent(interval=0.1) > threshold
            
            # Memory check: if:memory>80
            if condition.startswith("memory>"):
                import psutil
                threshold = int(condition.split(">")[1])
                return psutil.virtual_memory().percent > threshold
            
            # Disk check: if:disk>80
            if condition.startswith("disk>"):
                import psutil
                threshold = int(condition.split(">")[1])
                return psutil.disk_usage('/').percent > threshold
            
            return False
        
        return False
    
    async def execute_action(self, action: Dict[str, Any]):
        """Execute a workflow action"""
        action_type = action.get("type")
        
        if action_type == "command":
            command = action.get("command")
            logger.info(f"▶️ Executing command: {command}")
            
            # Execute command through AI Brain
            try:
                from ..ai_engine.enhanced_brain import get_enhanced_brain
                brain = await get_enhanced_brain()
                result = await brain.process_command(command)
                logger.success(f"✅ Command executed: {result.get('response', '')[:100]}")
            except Exception as e:
                logger.error(f"❌ Command execution failed: {e}")
            
        elif action_type == "optimize":
            logger.info("▶️ Optimizing system")
            
            # Trigger system optimization
            try:
                from ..hardware.optimizer import get_optimizer
                optimizer = await get_optimizer()
                result = await optimizer.optimize_all()
                logger.success(f"✅ System optimized")
            except Exception as e:
                logger.error(f"❌ Optimization failed: {e}")
            
        elif action_type == "notify":
            message = action.get("message")
            logger.info(f"▶️ Sending notification: {message}")
            
            # Send desktop notification (if available)
            try:
                import subprocess
                subprocess.run(['notify-send', 'KI-ana OS', message], check=False)
                logger.success("✅ Notification sent")
            except Exception as e:
                logger.warning(f"⚠️ Notification failed (no display): {e}")
        
        elif action_type == "log":
            message = action.get("message")
            logger.info(f"📝 Log: {message}")
        
        elif action_type == "scan":
            logger.info("▶️ Scanning hardware")
            try:
                from ..hardware.scanner import get_scanner
                scanner = await get_scanner()
                result = await scanner.full_scan()
                logger.success(f"✅ Hardware scanned: {len(result)} devices")
            except Exception as e:
                logger.error(f"❌ Scan failed: {e}")
    
    async def run_workflow(self, workflow: Workflow):
        """Run a workflow's actions"""
        logger.info(f"🔄 Running workflow: {workflow.name}")
        
        for action in workflow.actions:
            await self.execute_action(action)
    
    async def monitor(self, context: Dict[str, Any]):
        """Monitor and execute workflows"""
        for workflow in self.workflows:
            if not workflow.enabled:
                continue
            
            if await self.check_trigger(workflow, context):
                await self.run_workflow(workflow)
    
    def get_workflows(self) -> List[Dict[str, Any]]:
        """Get all workflows"""
        return [
            {
                "name": w.name,
                "trigger": w.trigger,
                "actions": w.actions,
                "enabled": w.enabled
            }
            for w in self.workflows
        ]
