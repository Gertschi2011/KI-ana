"""
Smart Brain - LLM-Powered AI Brain

The most advanced version with full LLM integration.
"""

import asyncio
from typing import Dict, Any
from loguru import logger
from .enhanced_brain import EnhancedAIBrain
from ..nlp.intent_llm import LLMIntentRecognizer
from ..nlp.response_generator import ResponseGenerator


class SmartBrain(EnhancedAIBrain):
    """
    Smart Brain with LLM-powered intelligence
    
    Replaces keyword matching with actual AI understanding.
    Generates natural, context-aware responses.
    """
    
    def __init__(self):
        super().__init__()
        
        # Replace intent recognizer with LLM version
        self.llm_intent_recognizer = LLMIntentRecognizer()
        self.response_generator = ResponseGenerator()
        
    async def initialize(self):
        """Initialize with LLM components"""
        logger.info("🧠 Initializing Smart Brain (LLM-powered)...")
        
        # Initialize LLM components first
        await self.llm_intent_recognizer.initialize()
        await self.response_generator.initialize()
        
        # Then initialize base (hardware, mother-ki, etc.)
        await super().initialize()
        
        logger.success("✅ Smart Brain ready with full LLM power!")
        
    async def process_command(self, user_input: str) -> Dict[str, Any]:
        """
        Process command with LLM-powered intelligence
        """
        if not self.is_ready:
            return {
                "success": False,
                "error": "Smart Brain not initialized yet"
            }
        
        logger.info(f"🧠 Processing: {user_input}")
        
        try:
            # 1. Get context
            context = await self.context_manager.get_context()
            
            # 2. Use LLM to recognize intent
            intent = await self.llm_intent_recognizer.recognize(user_input, context)
            
            llm_status = "🤖 LLM" if intent.get("llm_used") else "📝 Fallback"
            logger.info(f"{llm_status} Intent: {intent['action']} (confidence: {intent.get('confidence', 0):.2f})")
            
            # 3. Check for hardware-specific commands
            if self._is_hardware_command(user_input):
                result = await self._handle_hardware_command(user_input)
            else:
                # 4. Dispatch action
                result = await self.action_dispatcher.dispatch(intent, context)
            
            # 5. Generate response with LLM
            response = await self.response_generator.generate(intent, result, context)
            
            # 6. Update context
            await self.context_manager.update(user_input, intent, result)
            
            return {
                "success": True,
                "intent": intent,
                "result": result,
                "response": response
            }
            
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": f"Entschuldigung, da ist etwas schief gelaufen: {e}"
            }


# Singleton
_smart_brain_instance = None


async def get_smart_brain() -> SmartBrain:
    """Get or create Smart Brain singleton"""
    global _smart_brain_instance
    
    if _smart_brain_instance is None:
        _smart_brain_instance = SmartBrain()
        await _smart_brain_instance.initialize()
    
    return _smart_brain_instance
