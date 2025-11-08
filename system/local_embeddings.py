"""
Local Embeddings Service

Generates embeddings locally using sentence-transformers instead of OpenAI.
Supports multiple models with different size/quality tradeoffs.

Models:
- all-MiniLM-L6-v2: Fast, small (80MB), good for most use cases
- all-mpnet-base-v2: Slower, larger (420MB), better quality
- multilingual-e5-base: Multilingual support (1.1GB)
"""
from __future__ import annotations
import time
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
import numpy as np


@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""
    text: str
    embedding: List[float]
    model: str
    dimension: int
    generation_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "embedding": self.embedding,
            "model": self.model,
            "dimension": self.dimension,
            "generation_time": self.generation_time
        }


class LocalEmbeddingService:
    """
    Local embedding service using sentence-transformers.
    
    Singleton pattern to avoid loading models multiple times.
    """
    
    _instance: Optional['LocalEmbeddingService'] = None
    
    # Available models with their characteristics
    MODELS = {
        "mini": {
            "name": "all-MiniLM-L6-v2",
            "dimension": 384,
            "size_mb": 80,
            "speed": "fast",
            "quality": "good"
        },
        "base": {
            "name": "all-mpnet-base-v2",
            "dimension": 768,
            "size_mb": 420,
            "speed": "medium",
            "quality": "better"
        },
        "multilingual": {
            "name": "intfloat/multilingual-e5-base",
            "dimension": 768,
            "size_mb": 1100,
            "speed": "medium",
            "quality": "best"
        }
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.models: Dict[str, SentenceTransformer] = {}
        self.cache_dir = Path.home() / "ki_ana" / "models" / "embeddings"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Default model
        self.default_model = os.getenv("EMBEDDING_MODEL", "mini")
        
        # Load default model on init
        self._load_model(self.default_model)
    
    def _load_model(self, model_key: str) -> SentenceTransformer:
        """Load a model if not already loaded."""
        if model_key in self.models:
            return self.models[model_key]
        
        if model_key not in self.MODELS:
            raise ValueError(f"Unknown model: {model_key}. Available: {list(self.MODELS.keys())}")
        
        model_name = self.MODELS[model_key]["name"]
        print(f"Loading embedding model: {model_name}...")
        
        start = time.time()
        model = SentenceTransformer(model_name, cache_folder=str(self.cache_dir))
        load_time = time.time() - start
        
        self.models[model_key] = model
        print(f"✅ Model loaded in {load_time:.2f}s")
        
        return model
    
    def embed(
        self,
        text: str,
        model: str = None,
        normalize: bool = True
    ) -> EmbeddingResult:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            model: Model to use (mini/base/multilingual), defaults to configured default
            normalize: Whether to normalize embeddings (recommended for similarity search)
        
        Returns:
            EmbeddingResult with embedding vector and metadata
        """
        model_key = model or self.default_model
        model_obj = self._load_model(model_key)
        
        start = time.time()
        embedding = model_obj.encode(
            text,
            normalize_embeddings=normalize,
            show_progress_bar=False
        )
        generation_time = time.time() - start
        
        return EmbeddingResult(
            text=text,
            embedding=embedding.tolist(),
            model=self.MODELS[model_key]["name"],
            dimension=len(embedding),
            generation_time=generation_time
        )
    
    def embed_batch(
        self,
        texts: List[str],
        model: str = None,
        normalize: bool = True,
        batch_size: int = 32
    ) -> List[EmbeddingResult]:
        """
        Generate embeddings for multiple texts (more efficient than single calls).
        
        Args:
            texts: List of texts to embed
            model: Model to use
            normalize: Whether to normalize embeddings
            batch_size: Batch size for processing
        
        Returns:
            List of EmbeddingResult objects
        """
        if not texts:
            return []
        
        model_key = model or self.default_model
        model_obj = self._load_model(model_key)
        
        start = time.time()
        embeddings = model_obj.encode(
            texts,
            normalize_embeddings=normalize,
            show_progress_bar=len(texts) > 100,
            batch_size=batch_size
        )
        total_time = time.time() - start
        avg_time = total_time / len(texts)
        
        results = []
        for text, embedding in zip(texts, embeddings):
            results.append(EmbeddingResult(
                text=text,
                embedding=embedding.tolist(),
                model=self.MODELS[model_key]["name"],
                dimension=len(embedding),
                generation_time=avg_time
            ))
        
        return results
    
    def similarity(
        self,
        text1: str,
        text2: str,
        model: str = None
    ) -> float:
        """
        Calculate cosine similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
            model: Model to use
        
        Returns:
            Similarity score between -1 and 1 (higher = more similar)
        """
        emb1 = self.embed(text1, model=model, normalize=True)
        emb2 = self.embed(text2, model=model, normalize=True)
        
        # Cosine similarity (already normalized, so just dot product)
        similarity = np.dot(emb1.embedding, emb2.embedding)
        
        return float(similarity)
    
    def get_model_info(self, model: str = None) -> Dict[str, Any]:
        """Get information about a model."""
        model_key = model or self.default_model
        if model_key not in self.MODELS:
            raise ValueError(f"Unknown model: {model_key}")
        
        info = self.MODELS[model_key].copy()
        info["loaded"] = model_key in self.models
        info["key"] = model_key
        
        return info
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List all available models."""
        return [
            {
                "key": key,
                "loaded": key in self.models,
                **info
            }
            for key, info in self.MODELS.items()
        ]
    
    def benchmark(self, text: str = None, iterations: int = 10) -> Dict[str, Any]:
        """
        Benchmark embedding generation performance.
        
        Args:
            text: Text to use for benchmark (default: sample text)
            iterations: Number of iterations
        
        Returns:
            Benchmark results with timing statistics
        """
        if text is None:
            text = "This is a sample text for benchmarking the embedding generation performance."
        
        results = {}
        
        for model_key in self.MODELS.keys():
            times = []
            
            # Warmup
            self.embed(text, model=model_key)
            
            # Benchmark
            for _ in range(iterations):
                result = self.embed(text, model=model_key)
                times.append(result.generation_time)
            
            results[model_key] = {
                "model": self.MODELS[model_key]["name"],
                "avg_time": np.mean(times),
                "min_time": np.min(times),
                "max_time": np.max(times),
                "std_time": np.std(times),
                "dimension": self.MODELS[model_key]["dimension"]
            }
        
        return results


# Singleton instance
_service: Optional[LocalEmbeddingService] = None


def get_embedding_service() -> LocalEmbeddingService:
    """Get the singleton embedding service instance."""
    global _service
    if _service is None:
        _service = LocalEmbeddingService()
    return _service


# Convenience functions
def embed(text: str, model: str = None) -> List[float]:
    """Generate embedding for text (convenience function)."""
    service = get_embedding_service()
    result = service.embed(text, model=model)
    return result.embedding


def embed_batch(texts: List[str], model: str = None) -> List[List[float]]:
    """Generate embeddings for multiple texts (convenience function)."""
    service = get_embedding_service()
    results = service.embed_batch(texts, model=model)
    return [r.embedding for r in results]


def similarity(text1: str, text2: str, model: str = None) -> float:
    """Calculate similarity between two texts (convenience function)."""
    service = get_embedding_service()
    return service.similarity(text1, text2, model=model)


if __name__ == "__main__":
    # Quick test
    print("🔤 Local Embeddings Service Test\n")
    
    service = get_embedding_service()
    
    # List models
    print("Available models:")
    for model in service.list_models():
        print(f"  - {model['key']}: {model['name']} ({model['dimension']}d, {model['size_mb']}MB)")
    
    # Test embedding
    print("\n📊 Testing embedding generation...")
    text = "KI_ana ist ein intelligenter Assistent mit lokalen Modellen."
    result = service.embed(text)
    print(f"✅ Generated {result.dimension}d embedding in {result.generation_time*1000:.1f}ms")
    
    # Test similarity
    print("\n🔍 Testing similarity...")
    text1 = "KI_ana läuft lokal auf deinem Computer."
    text2 = "Der Assistent funktioniert offline ohne Cloud."
    text3 = "Pizza ist ein italienisches Gericht."
    
    sim12 = service.similarity(text1, text2)
    sim13 = service.similarity(text1, text3)
    
    print(f"Similarity (related):   {sim12:.3f}")
    print(f"Similarity (unrelated): {sim13:.3f}")
    
    # Benchmark
    print("\n⚡ Running benchmark...")
    bench = service.benchmark(iterations=5)
    for model_key, stats in bench.items():
        print(f"{model_key:12} - {stats['avg_time']*1000:6.1f}ms avg ({stats['dimension']}d)")
