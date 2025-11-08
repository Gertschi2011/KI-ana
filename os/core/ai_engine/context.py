"""
Context Manager

Manages system and conversation context.
"""

from typing import Dict, Any, List
from loguru import logger
from datetime import datetime


class ContextManager:
    """
    Manages context for intelligent decision making
    
    Keeps track of:
    - Current system state
    - User preferences
    - Conversation history
    - Recent actions
    """
    
    def __init__(self):
        self.system_context: Dict[str, Any] = {}
        self.conversation_history: List[Dict] = []
        self.user_preferences: Dict[str, Any] = {}
        
    async def initialize(self):
        """Initialize context manager"""
        logger.info("🗂️  Initializing Context Manager...")
        
        # Load initial context
        self.system_context = {
            "boot_time": datetime.now().isoformat(),
            "session_id": self._generate_session_id()
        }
        
        logger.success("✅ Context Manager ready")
        
    async def get_context(self) -> Dict[str, Any]:
        """Get current context"""
        return {
            "system": self.system_context,
            "preferences": self.user_preferences,
            "recent_history": self.conversation_history[-5:]  # Last 5 interactions
        }
    
    async def update(self, user_input: str, intent: Dict, result: Dict):
        """Update context after an interaction"""
        
        # Add to conversation history
        self.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "intent": intent.get("action"),
            "success": result.get("success", False)
        })
        
        # Keep only last 100 interactions
        if len(self.conversation_history) > 100:
            self.conversation_history = self.conversation_history[-100:]
        
        # Learn preferences (simple for now)
        await self._learn_preferences(user_input, intent, result)
        
    async def _learn_preferences(self, user_input: str, intent: Dict, result: Dict):
        """Learn user preferences from interactions"""
        
        # Example: Track frequently used commands
        action = intent.get("action")
        if action:
            if "frequent_commands" not in self.user_preferences:
                self.user_preferences["frequent_commands"] = {}
            
            freq = self.user_preferences["frequent_commands"]
            freq[action] = freq.get(action, 0) + 1
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        import uuid
        return str(uuid.uuid4())
