"""
Intent Recognition System

Understands what the user wants to do from natural language.
"""

from typing import Dict, Any, List
from loguru import logger


class IntentRecognizer:
    """
    Recognizes user intent from natural language
    
    This will later use LLMs, but for now uses keyword matching
    as a proof of concept.
    """
    
    def __init__(self):
        self.patterns = self._build_patterns()
        
    async def initialize(self):
        """Initialize the intent recognizer"""
        logger.info("🎯 Initializing Intent Recognizer...")
        # TODO: Load LLM model here
        logger.success("✅ Intent Recognizer ready")
        
    def _build_patterns(self) -> Dict[str, List[str]]:
        """Build keyword patterns for intent recognition"""
        return {
            "system_info": [
                "system", "info", "hardware", "specs", "cpu", "ram", "speicher"
            ],
            "optimize": [
                "optimiere", "optimize", "schneller", "faster", "performance", "langsam"
            ],
            "scan_hardware": [
                "scan", "hardware", "detect", "erkennen", "geräte"
            ],
            "install_driver": [
                "treiber", "driver", "install", "installiere"
            ],
            "help": [
                "help", "hilfe", "was kannst du", "befehle"
            ]
        }
    
    async def recognize(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recognize intent from user input
        
        Args:
            user_input: Natural language input
            context: Current system context
            
        Returns:
            Intent dictionary with action and parameters
        """
        user_input = user_input.lower()
        
        # Simple keyword matching for now
        for intent, keywords in self.patterns.items():
            if any(keyword in user_input for keyword in keywords):
                return {
                    "action": intent,
                    "confidence": 0.9,
                    "raw_input": user_input,
                    "parameters": self._extract_parameters(user_input, intent)
                }
        
        # Unknown intent
        return {
            "action": "unknown",
            "confidence": 0.0,
            "raw_input": user_input,
            "parameters": {}
        }
    
    def _extract_parameters(self, user_input: str, intent: str) -> Dict[str, Any]:
        """Extract parameters from user input based on intent"""
        params = {}
        
        # Intent-specific parameter extraction
        if intent == "install_driver":
            # Try to extract device name
            words = user_input.split()
            for i, word in enumerate(words):
                if word in ["für", "for"] and i + 1 < len(words):
                    params["device"] = words[i + 1]
        
        return params
