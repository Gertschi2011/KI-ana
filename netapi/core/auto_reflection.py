"""
Automatic Self-Reflection System

Triggers self-reflection automatically after N chat interactions.
Analyzes recent answers, detects contradictions, and creates
correction blocks.
"""
from __future__ import annotations
import time
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field
from collections import deque


@dataclass
class ReflectionTrigger:
    """Tracks when to trigger reflection."""
    answer_count: int = 0
    last_reflection_ts: float = 0.0
    recent_answers: deque = field(default_factory=lambda: deque(maxlen=15))
    reflection_count: int = 0
    
    def add_answer(self, answer: str, conv_id: str = "") -> None:
        """Add an answer to the history."""
        self.recent_answers.append({
            "text": answer[:500],  # Truncate for memory
            "ts": time.time(),
            "conv_id": conv_id
        })
        self.answer_count += 1
    
    def should_trigger(self, threshold: int = 10) -> bool:
        """Check if reflection should be triggered."""
        # Trigger every N answers
        if self.answer_count >= threshold:
            # Also check cooldown (don't reflect too often)
            cooldown = 300  # 5 minutes
            if time.time() - self.last_reflection_ts > cooldown:
                return True
        return False
    
    def reset_trigger(self) -> None:
        """Reset trigger after reflection."""
        self.answer_count = 0
        self.last_reflection_ts = time.time()
        self.reflection_count += 1


class AutoReflectionService:
    """Service for automatic self-reflection."""
    
    def __init__(self):
        self._trigger = ReflectionTrigger()
        self._enabled = True
        self._threshold = 10  # Trigger after N answers
        self._runtime_dir = Path.home() / "ki_ana" / "runtime"
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._runtime_dir / "auto_reflection_state.json"
        
        # Load state if exists
        self._load_state()
    
    def _load_state(self) -> None:
        """Load reflection state from disk."""
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text())
                self._trigger.answer_count = data.get("answer_count", 0)
                self._trigger.last_reflection_ts = data.get("last_reflection_ts", 0.0)
                self._trigger.reflection_count = data.get("reflection_count", 0)
        except Exception:
            pass
    
    def _save_state(self) -> None:
        """Save reflection state to disk."""
        try:
            data = {
                "answer_count": self._trigger.answer_count,
                "last_reflection_ts": self._trigger.last_reflection_ts,
                "reflection_count": self._trigger.reflection_count,
                "last_save": time.time()
            }
            self._state_file.write_text(json.dumps(data, indent=2))
        except Exception:
            pass
    
    def record_answer(self, answer: str, conv_id: str = "") -> None:
        """Record an answer for future reflection."""
        if not self._enabled:
            return
        
        self._trigger.add_answer(answer, conv_id)
        
        # Save state periodically
        if self._trigger.answer_count % 5 == 0:
            self._save_state()
    
    def check_and_trigger(self) -> Optional[Dict[str, Any]]:
        """
        Check if reflection should be triggered and execute it.
        Returns reflection result or None if not triggered.
        """
        if not self._enabled:
            return None
        
        if not self._trigger.should_trigger(self._threshold):
            return None
        
        # Trigger reflection!
        result = self._execute_reflection()
        
        # Reset trigger
        self._trigger.reset_trigger()
        self._save_state()
        
        return result
    
    def _execute_reflection(self) -> Dict[str, Any]:
        """Execute the actual reflection process."""
        try:
            # Import reflection engine
            import sys
            sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))
            from reflection_engine import analyze_recent_answers
            
            # Get recent answers
            answers = [a["text"] for a in self._trigger.recent_answers]
            
            if not answers:
                return {"ok": False, "reason": "no_answers"}
            
            # Analyze
            result = analyze_recent_answers(answers)
            
            # Store insights as a new block
            if result.get("insights"):
                self._store_reflection_block(result)
            
            return {
                "ok": True,
                "analyzed_answers": len(answers),
                "insights": result.get("insights", ""),
                "suggestions": result.get("suggestions", []),
                "timestamp": time.time()
            }
            
        except Exception as e:
            return {
                "ok": False,
                "reason": f"reflection_error: {str(e)}"
            }
    
    def _store_reflection_block(self, reflection_result: Dict[str, Any]) -> None:
        """Store reflection insights as a block."""
        try:
            from netapi.memory_store import add_block
            
            insights = reflection_result.get("insights", "")
            suggestions = reflection_result.get("suggestions", [])
            
            # Create content
            content_parts = [f"**Selbstreflexion #{self._trigger.reflection_count}**\n"]
            content_parts.append(f"Analysierte Antworten: {len(self._trigger.recent_answers)}\n")
            content_parts.append(f"\n**Erkenntnisse:**\n{insights}\n")
            
            if suggestions:
                content_parts.append(f"\n**Vorschläge ({len(suggestions)}):**")
                for i, sug in enumerate(suggestions, 1):
                    title = sug.get("title", "Ohne Titel")
                    content_parts.append(f"\n{i}. {title}")
            
            content = "\n".join(content_parts)
            
            # Store as block
            add_block(
                title=f"Selbstreflexion #{self._trigger.reflection_count}",
                content=content,
                tags=["reflection", "auto", "system", "self-improvement"],
                url=None,
                meta={
                    "type": "auto_reflection",
                    "analyzed_count": len(self._trigger.recent_answers),
                    "reflection_number": self._trigger.reflection_count,
                    "timestamp": time.time()
                }
            )
        except Exception:
            pass
    
    def enable(self) -> None:
        """Enable automatic reflection."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable automatic reflection."""
        self._enabled = False
    
    def is_enabled(self) -> bool:
        """Check if automatic reflection is enabled."""
        return self._enabled
    
    def set_threshold(self, n: int) -> None:
        """Set the threshold for triggering reflection."""
        self._threshold = max(3, min(50, n))  # Clamp between 3 and 50
    
    def get_stats(self) -> Dict[str, Any]:
        """Get reflection statistics."""
        return {
            "enabled": self._enabled,
            "threshold": self._threshold,
            "answer_count": self._trigger.answer_count,
            "next_reflection_in": max(0, self._threshold - self._trigger.answer_count),
            "total_reflections": self._trigger.reflection_count,
            "last_reflection": self._trigger.last_reflection_ts,
            "recent_answers_count": len(self._trigger.recent_answers)
        }
    
    def force_reflection(self) -> Dict[str, Any]:
        """Force reflection immediately (for testing)."""
        result = self._execute_reflection()
        self._trigger.reset_trigger()
        self._save_state()
        return result


# Global instance
_auto_reflection_service = AutoReflectionService()


def get_auto_reflection_service() -> AutoReflectionService:
    """Get the global auto-reflection service instance."""
    return _auto_reflection_service
