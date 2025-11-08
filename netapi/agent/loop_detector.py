"""
Loop Detection System for Agent

Tracks conversation patterns to detect and prevent response loops.
Provides intelligent fallback strategies when loops are detected.
"""
from __future__ import annotations
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ConversationState:
    """Track state of a conversation to detect loops."""
    conv_id: str
    fallback_count: int = 0
    last_fallback_ts: float = 0.0
    last_reply: str = ""
    reply_history: list = field(default_factory=list)  # Last 5 replies
    question_attempts: int = 0  # How many times user rephrased same question
    last_user_message: str = ""
    
    def add_reply(self, reply: str) -> None:
        """Add reply to history, keeping last 5."""
        self.reply_history.append(reply[:200])
        if len(self.reply_history) > 5:
            self.reply_history.pop(0)
        self.last_reply = reply[:200]
    
    def is_loop_detected(self) -> bool:
        """Detect if we're in a response loop."""
        # Check 1: Too many fallbacks in short time
        if self.fallback_count >= 3:
            return True
        
        # Check 2: Same reply repeated
        if len(self.reply_history) >= 2:
            if self.reply_history[-1] == self.reply_history[-2]:
                return True
        
        # Check 3: Alternating between 2 responses
        if len(self.reply_history) >= 4:
            if (self.reply_history[-1] == self.reply_history[-3] and
                self.reply_history[-2] == self.reply_history[-4]):
                return True
        
        return False
    
    def increment_fallback(self, current_ts: float) -> None:
        """Increment fallback counter with time-based reset."""
        # Reset counter if more than 60 seconds passed
        if current_ts - self.last_fallback_ts > 60:
            self.fallback_count = 0
        
        self.fallback_count += 1
        self.last_fallback_ts = current_ts
    
    def reset(self) -> None:
        """Reset loop detection state."""
        self.fallback_count = 0
        self.question_attempts = 0


class LoopDetector:
    """Global loop detection system for all conversations."""
    
    def __init__(self):
        self._states: Dict[str, ConversationState] = {}
        self._max_fallbacks_per_conv = 3
        self._fallback_cooldown_secs = 30
    
    def get_state(self, conv_id: str) -> ConversationState:
        """Get or create conversation state."""
        key = str(conv_id or "global")
        if key not in self._states:
            self._states[key] = ConversationState(conv_id=key)
        return self._states[key]
    
    def should_allow_fallback(self, conv_id: str, current_ts: float) -> Tuple[bool, str]:
        """
        Check if fallback should be allowed.
        Returns: (allow: bool, reason: str)
        """
        state = self.get_state(conv_id)
        
        # Check if in loop
        if state.is_loop_detected():
            return False, "loop_detected"
        
        # Check fallback cooldown
        time_since_last = current_ts - state.last_fallback_ts
        if time_since_last < self._fallback_cooldown_secs:
            return False, "cooldown_active"
        
        # Check max fallbacks
        if state.fallback_count >= self._max_fallbacks_per_conv:
            return False, "max_fallbacks_reached"
        
        return True, "ok"
    
    def record_reply(self, conv_id: str, reply: str, is_fallback: bool = False) -> None:
        """Record a reply for loop detection."""
        state = self.get_state(conv_id)
        state.add_reply(reply)
        
        if is_fallback:
            state.increment_fallback(time.time())
    
    def record_user_message(self, conv_id: str, message: str) -> None:
        """Record user message to detect rephrasing."""
        state = self.get_state(conv_id)
        
        # Simple similarity check (can be improved)
        if state.last_user_message:
            msg_lower = message.lower()
            last_lower = state.last_user_message.lower()
            
            # Count common words
            msg_words = set(msg_lower.split())
            last_words = set(last_lower.split())
            if len(msg_words) > 0 and len(last_words) > 0:
                overlap = len(msg_words & last_words) / max(len(msg_words), len(last_words))
                
                # If >60% overlap, likely rephrasing same question
                if overlap > 0.6:
                    state.question_attempts += 1
                else:
                    state.question_attempts = 0
        
        state.last_user_message = message[:200]
    
    def get_escape_strategy(self, conv_id: str) -> str:
        """Get strategy to escape from loop."""
        state = self.get_state(conv_id)
        
        strategies = [
            "Lass uns das anders angehen. Was ist dein konkretes Ziel? Was möchtest du damit erreichen?",
            "Ich merke, wir kommen nicht weiter. Kann ich dir helfen, die Frage anders zu formulieren?",
            "Vielleicht hilft es, wenn du mir ein konkretes Beispiel gibst?",
            "Lass uns einen Schritt zurückgehen. Was ist der Kontext deiner Frage?",
        ]
        
        # Rotate through strategies
        idx = min(state.fallback_count, len(strategies) - 1)
        return strategies[idx]
    
    def reset_conversation(self, conv_id: str) -> None:
        """Reset conversation state (for testing or explicit reset)."""
        state = self.get_state(conv_id)
        state.reset()
    
    def cleanup_old_conversations(self, max_age_secs: float = 3600) -> None:
        """Remove old conversation states to prevent memory leak."""
        current_ts = time.time()
        to_remove = []
        
        for conv_id, state in self._states.items():
            if current_ts - state.last_fallback_ts > max_age_secs:
                to_remove.append(conv_id)
        
        for conv_id in to_remove:
            del self._states[conv_id]


# Global instance
_loop_detector = LoopDetector()


def get_loop_detector() -> LoopDetector:
    """Get global loop detector instance."""
    return _loop_detector
