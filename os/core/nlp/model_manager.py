"""
Model Manager

Manages multiple LLM models and allows switching between them.
"""

from typing import Dict, Any, List, Optional
from loguru import logger
from .llm_client import LLMClient


class ModelProfile:
    """Profile for an LLM model"""
    
    def __init__(self, 
                 name: str,
                 model_name: str,
                 description: str,
                 use_case: str,
                 speed: str,
                 quality: str,
                 size_gb: float):
        self.name = name
        self.model_name = model_name
        self.description = description
        self.use_case = use_case
        self.speed = speed  # fast, medium, slow
        self.quality = quality  # good, better, best
        self.size_gb = size_gb


class ModelManager:
    """
    Multi-Model Manager
    
    Manages multiple LLM models:
    - Switch between models
    - Compare models
    - Optimize for task
    - Performance profiles
    """
    
    def __init__(self):
        self.models = self._initialize_models()
        self.current_model = "llama3.1:8b"
        self.clients: Dict[str, LLMClient] = {}
        
    def _initialize_models(self) -> Dict[str, ModelProfile]:
        """Initialize available models"""
        return {
            "llama3.1:8b": ModelProfile(
                name="Llama 3.1 8B",
                model_name="llama3.1:8b",
                description="Fast, balanced model for general tasks",
                use_case="General purpose, quick responses",
                speed="fast",
                quality="good",
                size_gb=4.7
            ),
            "llama3.1:70b": ModelProfile(
                name="Llama 3.1 70B",
                model_name="llama3.1:70b",
                description="High-quality model for complex tasks",
                use_case="Complex reasoning, detailed responses",
                speed="slow",
                quality="best",
                size_gb=40.0
            ),
            "mistral:7b": ModelProfile(
                name="Mistral 7B",
                model_name="mistral:7b",
                description="Efficient model with good performance",
                use_case="Fast responses, coding tasks",
                speed="fast",
                quality="better",
                size_gb=4.1
            ),
            "codellama:13b": ModelProfile(
                name="Code Llama 13B",
                model_name="codellama:13b",
                description="Specialized for code and technical tasks",
                use_case="Programming, technical documentation",
                speed="medium",
                quality="better",
                size_gb=7.4
            ),
            "phi3:mini": ModelProfile(
                name="Phi-3 Mini",
                model_name="phi3:mini",
                description="Ultra-fast, lightweight model",
                use_case="Quick queries, low resource usage",
                speed="very_fast",
                quality="good",
                size_gb=2.3
            )
        }
    
    async def get_client(self, model_name: Optional[str] = None) -> LLMClient:
        """Get LLM client for specified model"""
        if model_name is None:
            model_name = self.current_model
        
        # Create client if not exists
        if model_name not in self.clients:
            client = LLMClient(model=model_name)
            await client.initialize()
            self.clients[model_name] = client
        
        return self.clients[model_name]
    
    def switch_model(self, model_name: str) -> bool:
        """Switch to different model"""
        if model_name not in self.models:
            logger.error(f"Model {model_name} not found")
            return False
        
        logger.info(f"🔄 Switching to model: {model_name}")
        self.current_model = model_name
        return True
    
    def get_model_info(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Get information about a model"""
        if model_name is None:
            model_name = self.current_model
        
        if model_name not in self.models:
            return {"error": "Model not found"}
        
        profile = self.models[model_name]
        return {
            "name": profile.name,
            "model_name": profile.model_name,
            "description": profile.description,
            "use_case": profile.use_case,
            "speed": profile.speed,
            "quality": profile.quality,
            "size_gb": profile.size_gb
        }
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List all available models"""
        return [self.get_model_info(name) for name in self.models.keys()]
    
    def recommend_model(self, task_type: str) -> str:
        """Recommend best model for task type"""
        recommendations = {
            "quick": "phi3:mini",
            "general": "llama3.1:8b",
            "complex": "llama3.1:70b",
            "code": "codellama:13b",
            "fast": "mistral:7b"
        }
        
        return recommendations.get(task_type.lower(), self.current_model)
    
    def get_current_model(self) -> str:
        """Get currently active model"""
        return self.current_model
    
    async def compare_models(self, prompt: str, models: List[str]) -> Dict[str, Any]:
        """Compare responses from multiple models"""
        logger.info(f"🔍 Comparing {len(models)} models...")
        
        results = {}
        
        for model_name in models:
            if model_name not in self.models:
                continue
            
            try:
                client = await self.get_client(model_name)
                
                import time
                start = time.time()
                response = await client.generate(prompt, temperature=0.7)
                duration = time.time() - start
                
                results[model_name] = {
                    "response": response,
                    "duration_seconds": round(duration, 2),
                    "model_info": self.get_model_info(model_name)
                }
            except Exception as e:
                logger.error(f"Error with {model_name}: {e}")
                results[model_name] = {"error": str(e)}
        
        return results


# Singleton
_model_manager_instance: Optional[ModelManager] = None


async def get_model_manager() -> ModelManager:
    """Get or create ModelManager singleton"""
    global _model_manager_instance
    
    if _model_manager_instance is None:
        _model_manager_instance = ModelManager()
    
    return _model_manager_instance
