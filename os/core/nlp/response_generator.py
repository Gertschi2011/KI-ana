"""
Response Generator

Generates natural, context-aware responses using LLM.
"""

from typing import Dict, Any
from loguru import logger
from .llm_client import get_llm_client


class ResponseGenerator:
    """
    LLM-powered Response Generator
    
    Generates human-like, context-aware responses instead of templates.
    """
    
    def __init__(self):
        self.llm = None
        self.system_prompt = self._build_system_prompt()
        
    async def initialize(self):
        """Initialize LLM client"""
        logger.info("💬 Initializing Response Generator...")
        try:
            self.llm = await get_llm_client()
            if self.llm.is_available:
                logger.success("✅ Response Generator ready")
            else:
                logger.warning("⚠️  LLM not available, using templates")
        except Exception as e:
            logger.warning(f"Response generator init failed: {e}")
            self.llm = None
    
    def _build_system_prompt(self) -> str:
        """System prompt for response generation"""
        return """You are KI-ana, an AI Operating System assistant.

Your personality:
- Friendly and helpful
- Technical but not intimidating
- Confident but not arrogant
- Use emojis sparingly (1-2 per response)
- Keep responses concise (2-3 sentences max)
- Speak German naturally

Your job is to explain system actions in a friendly, understandable way.

Be direct and helpful. If something worked, say so. If it failed, explain why and what to do next."""
    
    async def generate(self, intent: Dict[str, Any], result: Dict[str, Any], context: Dict[str, Any]) -> str:
        """
        Generate natural response based on action result
        
        Args:
            intent: Recognized intent
            result: Action execution result
            context: Current context
            
        Returns:
            Natural language response
        """
        # If LLM not available, use template
        if not self.llm or not self.llm.is_available:
            return self._template_response(intent, result)
        
        try:
            # Build prompt
            action = intent.get("action", "unknown")
            success = result.get("success", False)
            data = result.get("data", {})
            error = result.get("error", "")
            
            prompt = f"""Action: {action}
Success: {success}
Data: {data}
Error: {error}

Generate a friendly, concise response for the user."""
            
            response = await self.llm.generate(
                prompt=prompt,
                system=self.system_prompt,
                temperature=0.7
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return self._template_response(intent, result)
    
    def _template_response(self, intent: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Fallback template responses"""
        if not result.get("success"):
            return f"Das hat leider nicht geklappt: {result.get('error', 'Unbekannter Fehler')}"
        
        action = intent.get("action", "unknown")
        
        templates = {
            "system_info": "Hier sind deine System-Informationen! 📊",
            "optimize": "System optimiert! 🚀",
            "scan_hardware": "Hardware-Scan abgeschlossen! 🔍",
            "install_driver": "Treiber installiert! 📦",
            "help": "Hier ist Hilfe! ❓",
            "unknown": "Erledigt! ✅"
        }
        
        return templates.get(action, templates["unknown"])
