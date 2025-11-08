"""
LLM Client - Ollama Integration

Interface to local LLM via Ollama.
"""

import aiohttp
from typing import Dict, Any, Optional, AsyncIterator
from loguru import logger
import json


class LLMClient:
    """
    Client for Ollama LLM
    
    Provides interface to local language models for:
    - Intent understanding
    - Response generation
    - Context-aware decisions
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1:8b"):
        self.base_url = base_url
        self.model = model
        self.session: Optional[aiohttp.ClientSession] = None
        self.is_available = False
        
    async def initialize(self):
        """Initialize LLM client and check availability"""
        logger.info(f"🤖 Initializing LLM client (model: {self.model})...")
        
        self.session = aiohttp.ClientSession()
        
        # Check if Ollama is running
        try:
            async with self.session.get(
                f"{self.base_url}/api/tags", 
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    
                    if self.model in models or self.model.split(":")[0] in [m.split(":")[0] for m in models]:
                        self.is_available = True
                        logger.success(f"✅ LLM client ready ({self.model})")
                    else:
                        logger.warning(f"Model {self.model} not found. Available: {models}")
                        logger.info("Run: ollama pull llama3.1:8b")
                        self.is_available = False
                else:
                    logger.warning("Ollama is running but returned error")
                    self.is_available = False
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            logger.info("Install Ollama: curl -fsSL https://ollama.com/install.sh | sh")
            self.is_available = False
    
    async def generate(self, prompt: str, system: Optional[str] = None, temperature: float = 0.7) -> str:
        """
        Generate completion from LLM
        
        Args:
            prompt: User prompt
            system: System prompt (context)
            temperature: Creativity (0.0 = deterministic, 1.0 = creative)
            
        Returns:
            Generated text
        """
        if not self.is_available:
            raise Exception("LLM not available")
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        if system:
            payload["system"] = system
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("response", "").strip()
                else:
                    error_text = await response.text()
                    logger.error(f"LLM request failed: {response.status} - {error_text}")
                    raise Exception(f"LLM request failed: {response.status}")
                    
        except aiohttp.ClientError as e:
            logger.error(f"LLM connection error: {e}")
            raise Exception(f"LLM connection error: {e}")
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise
    
    async def chat(self, messages: list, temperature: float = 0.7) -> str:
        """
        Chat completion (conversation)
        
        Args:
            messages: List of {role: str, content: str}
            temperature: Creativity
            
        Returns:
            Response text
        """
        if not self.is_available:
            raise Exception("LLM not available")
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("message", {}).get("content", "").strip()
                else:
                    error_text = await response.text()
                    logger.error(f"Chat request failed: {response.status} - {error_text}")
                    raise Exception(f"Chat request failed: {response.status}")
                    
        except aiohttp.ClientError as e:
            logger.error(f"Chat connection error: {e}")
            raise Exception(f"Chat connection error: {e}")
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            raise
    
    async def stream_generate(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        """Stream generation (for real-time responses)"""
        if not self.is_available:
            raise Exception("LLM not available")
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True
        }
        
        if system:
            payload["system"] = system
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=60
            ) as response:
                if response.status == 200:
                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line.decode())
                                chunk = data.get("response", "")
                                if chunk:
                                    yield chunk
                            except:
                                pass
                else:
                    raise Exception(f"Stream failed: {response.status}")
                    
        except Exception as e:
            logger.error(f"Stream generation failed: {e}")
            raise
    
    async def shutdown(self):
        """Cleanup"""
        if self.session:
            await self.session.close()


# Singleton
_llm_client_instance: Optional[LLMClient] = None


async def get_llm_client() -> LLMClient:
    """Get or create LLM client singleton"""
    global _llm_client_instance
    
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
        await _llm_client_instance.initialize()
    
    return _llm_client_instance
