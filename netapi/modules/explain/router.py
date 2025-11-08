"""
Explain API Router

Endpoints for accessing response explanations.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from .explainer import get_explainer

router = APIRouter(prefix="/api/explain", tags=["Explain"])


@router.get("/explanations")
async def list_explanations(
    limit: int = Query(50, ge=1, le=200)
):
    """
    List recent explanations.
    
    Returns a summary of recent response explanations.
    """
    try:
        explainer = get_explainer()
        explanations = explainer.list_recent_explanations(limit=limit)
        
        return {
            "ok": True,
            "count": len(explanations),
            "explanations": explanations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/explanations/{response_id}")
async def get_explanation(response_id: str):
    """
    Get detailed explanation for a specific response.
    
    Returns complete reasoning path, sources, tools, and SubMind contributions.
    """
    try:
        explainer = get_explainer()
        exp = explainer.get_explanation(response_id)
        
        if not exp:
            raise HTTPException(status_code=404, detail="Explanation not found")
        
        return {
            "ok": True,
            "explanation": exp.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_statistics():
    """
    Get explainer statistics.
    
    Returns metrics about explanations: total count, averages, etc.
    """
    try:
        explainer = get_explainer()
        stats = explainer.get_statistics()
        
        return {
            "ok": True,
            "statistics": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def create_test_explanation():
    """
    Create a test explanation for demo purposes.
    
    Returns the created explanation ID.
    """
    try:
        import hashlib
        import time
        
        explainer = get_explainer()
        
        # Create test explanation
        response_id = hashlib.md5(f"test_{time.time()}".encode()).hexdigest()[:12]
        exp = explainer.create_explanation(
            response_id=response_id,
            query="Test query",
            response="Test response",
            model_used="test_model",
            temperature=0.7
        )
        
        # Add sample data
        explainer.add_source(
            response_id,
            source_id="test_source_1",
            source_type="knowledge_block",
            content_snippet="Test content snippet",
            trust_score=0.85
        )
        
        explainer.add_reasoning_step(
            response_id,
            action="test_action",
            description="Test reasoning step",
            result="Test result"
        )
        
        explainer.finalize_explanation(response_id, total_duration_ms=100)
        explainer.save_explanation(exp)
        
        return {
            "ok": True,
            "response_id": response_id,
            "explanation": exp.to_dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
