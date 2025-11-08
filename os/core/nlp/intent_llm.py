"""
LLM-based Intent Recognition

Uses LLM to understand user intent from natural language.
"""

from typing import Dict, Any
from loguru import logger
from .llm_client import get_llm_client
import json


class LLMIntentRecognizer:
    """
    LLM-powered Intent Recognizer
    
    Uses language model to understand what user wants to do.
    Much smarter than keyword matching!
    """
    
    def __init__(self):
        self.llm = None
        self.system_prompt = self._build_system_prompt()
        
    async def initialize(self):
        """Initialize LLM client"""
        logger.info("🎯 Initializing LLM Intent Recognizer...")
        try:
            self.llm = await get_llm_client()
            if self.llm.is_available:
                logger.success("✅ LLM Intent Recognizer ready")
            else:
                logger.warning("⚠️ LLM not available, using fallback")
        except Exception as e:
            logger.warning(f"LLM init failed: {e}")
            self.llm = None
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for intent recognition"""
        return """You are an intent classifier for KI-ana OS, an AI operating system.

Your job is to understand what the user wants to do and classify their intent into one of these categories:

ACTIONS:
- system_info: User wants to see system information (CPU, RAM, etc.)
- optimize: User wants to optimize system performance
- scan_hardware: User wants to scan/detect hardware
- install_driver: User wants to install drivers
- check_health: User wants to check system health
- help: User needs help
- chat: General conversation
- unknown: Cannot determine intent

Respond ONLY with a valid JSON object in this format:
{
  "action": "action_name",
  "confidence": 0.0-1.0,
  "parameters": {},
  "reasoning": "brief explanation"
}

Be concise and accurate. No extra text, only JSON."""
    
    async def recognize(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recognize intent using LLM
        
        Args:
            user_input: Natural language input
            context: Current context
            
        Returns:
            Intent dictionary
        """
        # If LLM not available, use simple fallback
        if not self.llm or not self.llm.is_available:
            return self._fallback_recognition(user_input)
        
        try:
            # Prepare prompt
            prompt = f"""User said: "{user_input}"

Recent context: {json.dumps(context.get("recent_history", [])[-3:], indent=2)}

Classify the intent:"""
            
            # Get LLM response
            response = await self.llm.generate(
                prompt=prompt,
                system=self.system_prompt,
                temperature=0.3  # Low temperature for consistent classification
            )
            
            # Parse JSON response
            try:
                intent = json.loads(response)
                
                # Validate
                if "action" in intent:
                    return {
                        "action": intent.get("action", "unknown"),
                        "confidence": intent.get("confidence", 0.5),
                        "parameters": intent.get("parameters", {}),
                        "reasoning": intent.get("reasoning", ""),
                        "raw_input": user_input,
                        "llm_used": True
                    }
            except json.JSONDecodeError:
                logger.warning("LLM returned invalid JSON, using fallback")
                
        except Exception as e:
            logger.error(f"LLM intent recognition failed: {e}")
        
        # Fallback
        return self._fallback_recognition(user_input)
    
    def _fallback_recognition(self, user_input: str) -> Dict[str, Any]:
        """Simple keyword-based fallback"""
        user_input_lower = user_input.lower()
        
        # Simple keyword matching
        if any(word in user_input_lower for word in ["info", "system", "hardware", "cpu", "ram"]):
            return {"action": "system_info", "confidence": 0.7, "parameters": {}, "raw_input": user_input, "llm_used": False}
        elif any(word in user_input_lower for word in ["optimier", "schneller", "performance"]):
            return {"action": "optimize", "confidence": 0.7, "parameters": {}, "raw_input": user_input, "llm_used": False}
        elif any(word in user_input_lower for word in ["scan", "detect", "erkennen"]):
            return {"action": "scan_hardware", "confidence": 0.7, "parameters": {}, "raw_input": user_input, "llm_used": False}
        elif any(word in user_input_lower for word in ["treiber", "driver"]):
            return {"action": "install_driver", "confidence": 0.7, "parameters": {}, "raw_input": user_input, "llm_used": False}
        elif any(word in user_input_lower for word in ["hilfe", "help"]):
            return {"action": "help", "confidence": 0.9, "parameters": {}, "raw_input": user_input, "llm_used": False}
        else:
            return {"action": "chat", "confidence": 0.3, "parameters": {}, "raw_input": user_input, "llm_used": False}
