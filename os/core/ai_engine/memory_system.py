"""
Memory System

Long-term memory and learning for KI-ana OS.
"""

import json
from typing import Dict, Any, List
from pathlib import Path
from loguru import logger
from datetime import datetime


class MemorySystem:
    """
    Long-term Memory System
    
    Stores and retrieves:
    - Conversation history
    - User preferences
    - Learned patterns
    - Common tasks
    """
    
    def __init__(self, memory_file: str = "~/.kiana_memory.json"):
        self.memory_file = Path(memory_file).expanduser()
        self.memory: Dict[str, Any] = {
            "conversations": [],
            "preferences": {},
            "patterns": {},
            "common_tasks": [],
            "user_profile": {}
        }
        self.load_memory()
        
    def load_memory(self):
        """Load memory from disk"""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    self.memory = json.load(f)
                logger.info(f"📚 Loaded {len(self.memory.get('conversations', []))} conversations from memory")
            except Exception as e:
                logger.error(f"Failed to load memory: {e}")
    
    def save_memory(self):
        """Save memory to disk"""
        try:
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.memory_file, 'w') as f:
                json.dump(self.memory, f, indent=2)
            logger.debug("💾 Memory saved")
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
    
    def add_conversation(self, user_input: str, intent: str, response: str, success: bool):
        """Add conversation to history"""
        conv = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "intent": intent,
            "response": response,
            "success": success
        }
        
        self.memory["conversations"].append(conv)
        
        # Keep only last 1000 conversations
        if len(self.memory["conversations"]) > 1000:
            self.memory["conversations"] = self.memory["conversations"][-1000:]
        
        self.save_memory()
    
    def learn_preference(self, key: str, value: Any):
        """Learn user preference"""
        self.memory["preferences"][key] = value
        logger.info(f"📖 Learned preference: {key} = {value}")
        self.save_memory()
    
    def get_preference(self, key: str, default=None) -> Any:
        """Get user preference"""
        return self.memory["preferences"].get(key, default)
    
    def add_pattern(self, pattern_name: str, frequency: int = 1):
        """Track usage pattern"""
        if pattern_name in self.memory["patterns"]:
            self.memory["patterns"][pattern_name] += frequency
        else:
            self.memory["patterns"][pattern_name] = frequency
        
        self.save_memory()
    
    def get_common_patterns(self, limit: int = 10) -> List[tuple]:
        """Get most common patterns"""
        patterns = self.memory["patterns"].items()
        sorted_patterns = sorted(patterns, key=lambda x: x[1], reverse=True)
        return sorted_patterns[:limit]
    
    def suggest_next_action(self) -> str:
        """Suggest next action based on patterns"""
        patterns = self.get_common_patterns(5)
        if patterns:
            most_common = patterns[0][0]
            return f"Based on your usage, you might want to: {most_common}"
        return "No suggestions yet"
    
    def get_conversation_history(self, limit: int = 10) -> List[Dict]:
        """Get recent conversation history"""
        return self.memory["conversations"][-limit:]
    
    def update_user_profile(self, key: str, value: Any):
        """Update user profile"""
        self.memory["user_profile"][key] = value
        self.save_memory()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        return {
            "total_conversations": len(self.memory["conversations"]),
            "preferences_learned": len(self.memory["preferences"]),
            "patterns_tracked": len(self.memory["patterns"]),
            "most_common_action": self.get_common_patterns(1)[0] if self.memory["patterns"] else None
        }
