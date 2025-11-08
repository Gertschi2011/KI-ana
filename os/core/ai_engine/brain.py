"""
KI-ana OS AI Brain

The main AI brain that processes all user interactions and makes decisions.
"""

import asyncio
from typing import Optional, Dict, Any
from loguru import logger
from .intent import IntentRecognizer
from .action import ActionDispatcher
from .context import ContextManager
from ..error_handler import ErrorHandler, create_error_response, ErrorCategory


class AIBrain:
    """
    The AI Brain - Core intelligence of KI-ana OS
    
    This is the central controller that:
    - Understands user intent
    - Makes intelligent decisions
    - Executes actions
    - Learns from interactions
    """
    
    def __init__(self):
        logger.info("🧠 Initializing AI Brain...")
        
        self.intent_recognizer = IntentRecognizer()
        self.action_dispatcher = ActionDispatcher()
        self.context_manager = ContextManager()
        
        self.is_ready = False
        
    async def initialize(self):
        """Initialize all components"""
        logger.info("Starting AI Brain initialization...")
        
        # Initialize components
        await self.intent_recognizer.initialize()
        await self.action_dispatcher.initialize()
        await self.context_manager.initialize()
        
        self.is_ready = True
        logger.success("✅ AI Brain is ready!")
        
    async def process_command(self, user_input: str) -> Dict[str, Any]:
        """
        Process a natural language command from the user
        
        Args:
            user_input: Natural language input from user
            
        Returns:
            Result dictionary with action results and response
        """
        if not self.is_ready:
            return {
                "success": False,
                "error": "AI Brain not initialized yet"
            }
        
        logger.info(f"📝 Processing command: {user_input}")
        
        try:
            # 1. Get current context
            context = await self.context_manager.get_context()
            logger.debug(f"Context: {context}")
            
            # 2. Recognize intent
            intent = await self.intent_recognizer.recognize(user_input, context)
            logger.info(f"🎯 Recognized intent: {intent['action']}")
            
            # 3. Dispatch action
            result = await self.action_dispatcher.dispatch(intent, context)
            
            # 4. Update context (learn from interaction)
            await self.context_manager.update(user_input, intent, result)
            
            # 5. Generate response
            response = await self._generate_response(intent, result)
            
            return {
                "success": True,
                "intent": intent,
                "result": result,
                "response": response
            }
            
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            error_response = ErrorHandler.handle_error(e, context="process_command")
            error_response["response"] = f"❌ {error_response['error']}"
            if error_response.get("recovery_suggestions"):
                error_response["response"] += "\n\n💡 Vorschläge:\n" + "\n".join(
                    f"  • {s}" for s in error_response["recovery_suggestions"][:3]
                )
            return error_response
    
    async def _generate_response(self, intent: Dict, result: Dict) -> str:
        """Generate natural language response"""
        
        if not result.get("success"):
            return f"Das konnte ich leider nicht ausführen: {result.get('error', 'Unbekannter Fehler')}"
        
        # TODO: Use LLM to generate better responses
        action = intent.get("action", "unknown")
        
        responses = {
            "system_info": "Hier sind deine System-Informationen.",
            "optimize": "Ich habe dein System optimiert!",
            "scan_hardware": "Hardware-Scan abgeschlossen!",
            "unknown": "Ich habe das erledigt."
        }
        
        return responses.get(action, responses["unknown"])
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down AI Brain...")
        # Cleanup resources
        self.is_ready = False


# Singleton instance
_brain_instance: Optional[AIBrain] = None


async def get_brain() -> AIBrain:
    """Get or create AI Brain singleton"""
    global _brain_instance
    
    if _brain_instance is None:
        _brain_instance = AIBrain()
        await _brain_instance.initialize()
    
    return _brain_instance
