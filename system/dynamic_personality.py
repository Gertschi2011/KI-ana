"""
Dynamic Personality System

Allows the AI's personality to adapt based on:
1. User feedback (👍/👎)
2. Context (time of day, conversation history)
3. Success metrics
4. User mood detection

Core values (ethics) remain IMMUTABLE - only style traits adapt.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class DynamicPersonality:
    """Manages dynamic personality adjustments."""
    
    def __init__(self):
        self.base_dir = Path.home() / "ki_ana" / "system"
        self.profile_path = self.base_dir / "personality_profile.json"
        self.state_path = self.base_dir / "personality_state.json"
        
        # Load base profile (immutable)
        self.base_profile = self._load_json(self.profile_path)
        
        # Load/initialize state (mutable)
        self.state = self._load_or_init_state()
    
    def _load_json(self, path: Path) -> Dict[str, Any]:
        """Load JSON file."""
        try:
            if path.exists():
                return json.loads(path.read_text())
        except Exception:
            pass
        return {}
    
    def _load_or_init_state(self) -> Dict[str, Any]:
        """Load or initialize personality state."""
        state = self._load_json(self.state_path)
        
        # Initialize if empty or missing traits
        if not state or "traits" not in state:
            base_style = self.base_profile.get("style", {})
            state = {
                "version": "2.0",
                "created": datetime.now().isoformat(),
                "updated": datetime.now().isoformat(),
                "traits": {
                    # Copy style traits from base profile
                    trait: {
                        "value": float(value),
                        "adjustments": 0,
                        "last_feedback": None,
                        "history": []
                    }
                    for trait, value in base_style.items()
                },
                "context_modifiers": {
                    "time_of_day": {},
                    "user_mood": {}
                },
                "interactions": state.get("interactions", 0),
                "positive_feedback": 0,
                "negative_feedback": 0
            }
        
        return state
    
    def _save_state(self) -> None:
        """Save personality state to disk."""
        try:
            self.state["updated"] = datetime.now().isoformat()
            self.state_path.write_text(json.dumps(self.state, indent=2, ensure_ascii=False))
        except Exception:
            pass
    
    def get_current_traits(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """
        Get current trait values with context modifiers applied.
        
        Args:
            context: Optional context (time_of_day, user_mood, etc.)
        
        Returns:
            Dict of trait_name -> adjusted_value
        """
        traits = {}
        base_traits = self.state.get("traits", {})
        
        for trait_name, trait_data in base_traits.items():
            if isinstance(trait_data, dict):
                base_value = float(trait_data.get("value", 0.5))
            else:
                # Legacy format
                base_value = float(trait_data)
            
            # Apply context modifiers
            modified_value = self._apply_context_modifiers(
                trait_name, 
                base_value, 
                context or {}
            )
            
            # Clamp to [0.0, 1.0]
            traits[trait_name] = max(0.0, min(1.0, modified_value))
        
        # Add immutable values
        for value_name, value in self.base_profile.get("values", {}).items():
            traits[value_name] = float(value)
        
        return traits
    
    def _apply_context_modifiers(self, trait: str, base_value: float, context: Dict[str, Any]) -> float:
        """Apply context-based modifiers to a trait value."""
        value = base_value
        
        # Time of day modifiers
        hour = datetime.now().hour
        if trait == "empathy":
            # More empathetic in the evening
            if 18 <= hour < 23:
                value += 0.05
        elif trait == "humor":
            # Less humor late at night
            if 23 <= hour or hour < 6:
                value -= 0.1
        elif trait == "patience":
            # More patient in the morning
            if 6 <= hour < 12:
                value += 0.05
        
        # User mood modifiers (from context)
        user_mood = context.get("user_mood", "")
        if user_mood == "stressed":
            if trait == "empathy":
                value += 0.15
            elif trait == "patience":
                value += 0.10
            elif trait == "directness":
                value -= 0.10  # Be less direct when user is stressed
        elif user_mood == "curious":
            if trait == "explainability":
                value += 0.10
            elif trait == "curiosity":
                value += 0.05
        
        return value
    
    def adjust_from_feedback(self, feedback: str, traits_used: Optional[Dict[str, float]] = None) -> None:
        """
        Adjust personality based on user feedback.
        
        Args:
            feedback: 'positive' (👍) or 'negative' (👎)
            traits_used: Optional dict of traits that were active during this interaction
        """
        self.state["interactions"] = self.state.get("interactions", 0) + 1
        
        if feedback == "positive":
            self.state["positive_feedback"] = self.state.get("positive_feedback", 0) + 1
            delta_factor = 1.0
        elif feedback == "negative":
            self.state["negative_feedback"] = self.state.get("negative_feedback", 0) + 1
            delta_factor = -1.0
        else:
            return
        
        # Get feedback rules from base profile
        rules = self.base_profile.get("feedback_rules", {})
        boost = float(rules.get("praise_boost" if feedback == "positive" else "criticism_boost", 0.02))
        
        # Adjust traits that were used (or all if not specified)
        traits_to_adjust = traits_used.keys() if traits_used else self.state.get("traits", {}).keys()
        
        for trait_name in traits_to_adjust:
            if trait_name not in self.state.get("traits", {}):
                continue
            
            trait_data = self.state["traits"][trait_name]
            if not isinstance(trait_data, dict):
                # Convert legacy format
                trait_data = {
                    "value": float(trait_data),
                    "adjustments": 0,
                    "last_feedback": None,
                    "history": []
                }
                self.state["traits"][trait_name] = trait_data
            
            # Calculate adjustment
            current_value = float(trait_data.get("value", 0.5))
            delta = boost * delta_factor
            new_value = max(0.2, min(0.95, current_value + delta))
            
            # Update trait
            trait_data["value"] = new_value
            trait_data["adjustments"] = trait_data.get("adjustments", 0) + 1
            trait_data["last_feedback"] = datetime.now().isoformat()
            
            # Add to history (keep last 10)
            history = trait_data.get("history", [])
            history.append({
                "timestamp": datetime.now().isoformat(),
                "feedback": feedback,
                "delta": delta,
                "new_value": new_value
            })
            trait_data["history"] = history[-10:]  # Keep last 10
        
        self._save_state()
    
    def detect_user_mood(self, text: str) -> str:
        """
        Detect user mood from text (simple keyword-based).
        
        Returns: 'stressed', 'curious', 'happy', 'frustrated', or 'neutral'
        """
        text_lower = text.lower()
        
        # Stressed indicators
        if any(word in text_lower for word in [
            "schnell", "dringend", "hilfe", "problem", "geht nicht",
            "verstehe nicht", "funktioniert nicht", "fehler"
        ]):
            return "stressed"
        
        # Curious indicators
        if any(word in text_lower for word in [
            "wie", "warum", "wieso", "weshalb", "interessant",
            "erkläre", "erzähl", "mehr"
        ]):
            return "curious"
        
        # Happy indicators
        if any(word in text_lower for word in [
            "danke", "super", "toll", "perfekt", "genial", "👍", "😊"
        ]):
            return "happy"
        
        # Frustrated indicators
        if any(word in text_lower for word in [
            "ärgerlich", "nervt", "kompliziert", "egal", "vergiss es"
        ]):
            return "frustrated"
        
        return "neutral"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get personality statistics."""
        total = self.state.get("interactions", 0)
        positive = self.state.get("positive_feedback", 0)
        negative = self.state.get("negative_feedback", 0)
        
        return {
            "version": self.state.get("version", "2.0"),
            "created": self.state.get("created"),
            "updated": self.state.get("updated"),
            "interactions": total,
            "positive_feedback": positive,
            "negative_feedback": negative,
            "feedback_rate": positive / max(1, total),
            "traits": {
                name: {
                    "current_value": data.get("value") if isinstance(data, dict) else data,
                    "adjustments": data.get("adjustments", 0) if isinstance(data, dict) else 0
                }
                for name, data in self.state.get("traits", {}).items()
            }
        }
    
    def reset_trait(self, trait_name: str) -> bool:
        """Reset a trait to its base value."""
        try:
            base_value = self.base_profile.get("style", {}).get(trait_name)
            if base_value is None:
                return False
            
            if trait_name in self.state.get("traits", {}):
                trait_data = self.state["traits"][trait_name]
                if isinstance(trait_data, dict):
                    trait_data["value"] = float(base_value)
                    trait_data["adjustments"] = 0
                    trait_data["history"] = []
                else:
                    self.state["traits"][trait_name] = float(base_value)
                
                self._save_state()
                return True
        except Exception:
            pass
        return False
    
    def reset_all_traits(self) -> None:
        """Reset all traits to base values."""
        base_style = self.base_profile.get("style", {})
        for trait_name, base_value in base_style.items():
            self.reset_trait(trait_name)


# Global instance
_dynamic_personality = DynamicPersonality()


def get_dynamic_personality() -> DynamicPersonality:
    """Get the global dynamic personality instance."""
    return _dynamic_personality
