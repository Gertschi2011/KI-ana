"""
Local Embeddings API Router

Provides REST API for local embedding generation.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import sys
from pathlib import Path

# Add system path for imports
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

try:
    from local_embeddings import get_embedding_service, LocalEmbeddingService
    EMBEDDINGS_AVAILABLE = True
except Exception as e:
    print(f"Warning: Local embeddings not available: {e}")
    EMBEDDINGS_AVAILABLE = False

router = APIRouter(prefix="/api/embeddings", tags=["embeddings"])


# Request/Response Models
class EmbedRequest(BaseModel):
    """Request to generate embedding for text."""
    text: str = Field(..., description="Text to embed")
    model: Optional[str] = Field(None, description="Model to use (mini/base/multilingual)")
    normalize: bool = Field(True, description="Normalize embeddings")


class EmbedBatchRequest(BaseModel):
    """Request to generate embeddings for multiple texts."""
    texts: List[str] = Field(..., description="Texts to embed")
    model: Optional[str] = Field(None, description="Model to use")
    normalize: bool = Field(True, description="Normalize embeddings")
    batch_size: int = Field(32, description="Batch size for processing")


class SimilarityRequest(BaseModel):
    """Request to calculate similarity between two texts."""
    text1: str = Field(..., description="First text")
    text2: str = Field(..., description="Second text")
    model: Optional[str] = Field(None, description="Model to use")


class BenchmarkRequest(BaseModel):
    """Request to run embedding benchmark."""
    text: Optional[str] = Field(None, description="Text to use for benchmark")
    iterations: int = Field(10, description="Number of iterations")


# API Endpoints
@router.post("/embed")
async def embed_text(request: EmbedRequest):
    """Generate embedding for a single text."""
    if not EMBEDDINGS_AVAILABLE:
        raise HTTPException(503, "Local embeddings not available")
    
    try:
        service = get_embedding_service()
        result = service.embed(
            text=request.text,
            model=request.model,
            normalize=request.normalize
        )
        
        return {
            "ok": True,
            "result": result.to_dict()
        }
    except Exception as e:
        raise HTTPException(500, f"Embedding error: {e}")


@router.post("/embed/batch")
async def embed_batch(request: EmbedBatchRequest):
    """Generate embeddings for multiple texts."""
    if not EMBEDDINGS_AVAILABLE:
        raise HTTPException(503, "Local embeddings not available")
    
    try:
        service = get_embedding_service()
        results = service.embed_batch(
            texts=request.texts,
            model=request.model,
            normalize=request.normalize,
            batch_size=request.batch_size
        )
        
        return {
            "ok": True,
            "count": len(results),
            "results": [r.to_dict() for r in results]
        }
    except Exception as e:
        raise HTTPException(500, f"Batch embedding error: {e}")


@router.post("/similarity")
async def calculate_similarity(request: SimilarityRequest):
    """Calculate cosine similarity between two texts."""
    if not EMBEDDINGS_AVAILABLE:
        raise HTTPException(503, "Local embeddings not available")
    
    try:
        service = get_embedding_service()
        similarity = service.similarity(
            text1=request.text1,
            text2=request.text2,
            model=request.model
        )
        
        return {
            "ok": True,
            "similarity": similarity,
            "text1": request.text1,
            "text2": request.text2
        }
    except Exception as e:
        raise HTTPException(500, f"Similarity error: {e}")


@router.get("/models")
async def list_models():
    """List all available embedding models."""
    if not EMBEDDINGS_AVAILABLE:
        raise HTTPException(503, "Local embeddings not available")
    
    try:
        service = get_embedding_service()
        models = service.list_models()
        
        return {
            "ok": True,
            "models": models
        }
    except Exception as e:
        raise HTTPException(500, f"List models error: {e}")


@router.get("/models/{model_key}")
async def get_model_info(model_key: str):
    """Get information about a specific model."""
    if not EMBEDDINGS_AVAILABLE:
        raise HTTPException(503, "Local embeddings not available")
    
    try:
        service = get_embedding_service()
        info = service.get_model_info(model=model_key)
        
        return {
            "ok": True,
            "model": info
        }
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Model info error: {e}")


@router.post("/benchmark")
async def run_benchmark(request: BenchmarkRequest):
    """Run performance benchmark for all models."""
    if not EMBEDDINGS_AVAILABLE:
        raise HTTPException(503, "Local embeddings not available")
    
    try:
        service = get_embedding_service()
        results = service.benchmark(
            text=request.text,
            iterations=request.iterations
        )
        
        return {
            "ok": True,
            "iterations": request.iterations,
            "results": results
        }
    except Exception as e:
        raise HTTPException(500, f"Benchmark error: {e}")


@router.get("/stats")
async def get_stats():
    """Get embedding service statistics."""
    if not EMBEDDINGS_AVAILABLE:
        raise HTTPException(503, "Local embeddings not available")
    
    try:
        service = get_embedding_service()
        
        return {
            "ok": True,
            "stats": {
                "available": True,
                "default_model": service.default_model,
                "loaded_models": list(service.models.keys()),
                "cache_dir": str(service.cache_dir),
                "models": service.list_models()
            }
        }
    except Exception as e:
        raise HTTPException(500, f"Stats error: {e}")
