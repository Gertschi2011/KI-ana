"""
Local Vector Search API Router

Provides REST API for local vector search with Qdrant + local embeddings.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import sys
from pathlib import Path

# Add system path for imports
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

try:
    from local_vector_store import get_vector_store, SearchResult
    VECTOR_AVAILABLE = True
except Exception as e:
    print(f"Warning: Local vector store not available: {e}")
    VECTOR_AVAILABLE = False

router = APIRouter(prefix="/api/vector", tags=["vector"])


# Request/Response Models
class CreateCollectionRequest(BaseModel):
    """Request to create a new collection."""
    name: str = Field(..., description="Collection name")
    dimension: int = Field(384, description="Vector dimension (384 for mini, 768 for base)")
    distance: str = Field("Cosine", description="Distance metric (Cosine, Euclid, Dot)")
    recreate: bool = Field(False, description="Recreate if exists")


class AddTextsRequest(BaseModel):
    """Request to add texts to collection."""
    texts: List[str] = Field(..., description="Texts to add")
    metadatas: Optional[List[Dict[str, Any]]] = Field(None, description="Metadata for each text")
    ids: Optional[List[str]] = Field(None, description="IDs (auto-generated if not provided)")
    collection_name: Optional[str] = Field(None, description="Collection name")
    model: Optional[str] = Field(None, description="Embedding model")
    batch_size: int = Field(100, description="Batch size")


class SearchRequest(BaseModel):
    """Request to search in collection."""
    query: str = Field(..., description="Search query")
    collection_name: Optional[str] = Field(None, description="Collection name")
    limit: int = Field(5, description="Max results")
    score_threshold: float = Field(0.0, description="Min similarity score")
    filter_dict: Optional[Dict[str, Any]] = Field(None, description="Metadata filters")
    model: Optional[str] = Field(None, description="Embedding model")


# API Endpoints
@router.post("/collections/create")
async def create_collection(request: CreateCollectionRequest):
    """Create a new vector collection."""
    if not VECTOR_AVAILABLE:
        raise HTTPException(503, "Vector store not available")
    
    try:
        store = get_vector_store()
        success = store.create_collection(
            collection_name=request.name,
            dimension=request.dimension,
            distance=request.distance,
            recreate=request.recreate
        )
        
        return {
            "ok": True,
            "collection": request.name,
            "created": success
        }
    except Exception as e:
        raise HTTPException(500, f"Create collection error: {e}")


@router.get("/collections")
async def list_collections():
    """List all collections."""
    if not VECTOR_AVAILABLE:
        raise HTTPException(503, "Vector store not available")
    
    try:
        store = get_vector_store()
        collections = store.list_collections()
        
        return {
            "ok": True,
            "collections": collections,
            "count": len(collections)
        }
    except Exception as e:
        raise HTTPException(500, f"List collections error: {e}")


@router.get("/collections/{collection_name}")
async def get_collection_info(collection_name: str):
    """Get information about a collection."""
    if not VECTOR_AVAILABLE:
        raise HTTPException(503, "Vector store not available")
    
    try:
        store = get_vector_store()
        info = store.get_collection_info(collection_name)
        
        if info.get("exists") == False:
            raise HTTPException(404, f"Collection not found: {collection_name}")
        
        return {
            "ok": True,
            "info": info
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Get collection info error: {e}")


@router.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str):
    """Delete a collection."""
    if not VECTOR_AVAILABLE:
        raise HTTPException(503, "Vector store not available")
    
    try:
        store = get_vector_store()
        success = store.delete_collection(collection_name)
        
        return {
            "ok": True,
            "deleted": success,
            "collection": collection_name
        }
    except Exception as e:
        raise HTTPException(500, f"Delete collection error: {e}")


@router.post("/add")
async def add_texts(request: AddTextsRequest):
    """Add texts to vector collection with local embeddings."""
    if not VECTOR_AVAILABLE:
        raise HTTPException(503, "Vector store not available")
    
    try:
        store = get_vector_store()
        
        ids = store.add_texts(
            texts=request.texts,
            metadatas=request.metadatas,
            ids=request.ids,
            collection_name=request.collection_name,
            model=request.model,
            batch_size=request.batch_size
        )
        
        return {
            "ok": True,
            "added": len(ids),
            "ids": ids
        }
    except Exception as e:
        raise HTTPException(500, f"Add texts error: {e}")


@router.post("/search")
async def search(request: SearchRequest):
    """Search for similar texts using local embeddings."""
    if not VECTOR_AVAILABLE:
        raise HTTPException(503, "Vector store not available")
    
    try:
        store = get_vector_store()
        
        results = store.search(
            query=request.query,
            collection_name=request.collection_name,
            limit=request.limit,
            score_threshold=request.score_threshold,
            filter_dict=request.filter_dict,
            model=request.model
        )
        
        # Convert SearchResult objects to dicts
        results_dict = [
            {
                "id": r.id,
                "score": r.score,
                "text": r.text,
                "payload": r.payload
            }
            for r in results
        ]
        
        return {
            "ok": True,
            "query": request.query,
            "results": results_dict,
            "count": len(results_dict)
        }
    except Exception as e:
        raise HTTPException(500, f"Search error: {e}")


@router.get("/stats")
async def get_stats():
    """Get vector store statistics."""
    if not VECTOR_AVAILABLE:
        raise HTTPException(503, "Vector store not available")
    
    try:
        store = get_vector_store()
        collections = store.list_collections()
        
        collection_stats = []
        for col_name in collections:
            info = store.get_collection_info(col_name)
            if not info.get("error"):
                collection_stats.append({
                    "name": col_name,
                    "points": info.get("points_count", 0),
                    "dimension": info.get("config", {}).get("dimension"),
                    "distance": info.get("config", {}).get("distance")
                })
        
        return {
            "ok": True,
            "available": True,
            "qdrant_host": store.qdrant_host,
            "qdrant_port": store.qdrant_port,
            "collections": collection_stats,
            "total_collections": len(collections)
        }
    except Exception as e:
        raise HTTPException(500, f"Stats error: {e}")


@router.get("/health")
async def health_check():
    """Check if vector store is healthy."""
    if not VECTOR_AVAILABLE:
        return {
            "ok": False,
            "available": False,
            "error": "Vector store not available"
        }
    
    try:
        store = get_vector_store()
        # Try to list collections as health check
        collections = store.list_collections()
        
        return {
            "ok": True,
            "available": True,
            "qdrant_host": store.qdrant_host,
            "qdrant_port": store.qdrant_port,
            "collections_count": len(collections)
        }
    except Exception as e:
        return {
            "ok": False,
            "available": False,
            "error": str(e)
        }
