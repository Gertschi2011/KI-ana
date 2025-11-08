"""
Clean Chat Router - New Architecture

This is the NEW chat endpoint using the simplified, self-reflecting pipeline.
Runs parallel to the old router for comparison and gradual migration.

Endpoint: POST /api/v2/chat

Key Differences from old router:
1. No complex formatters or templates
2. Direct LLM answers with self-reflection
3. Clean, maintainable code
4. Proper logging and metrics
5. Part of the vision for autonomous AI

Migration Plan:
- Phase 1: Run parallel, A/B test
- Phase 2: Migrate users gradually
- Phase 3: Replace old router completely
"""

from __future__ import annotations
import time
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from netapi.deps import get_current_user_opt, get_db
from netapi.core.response_pipeline import ResponsePipeline, create_default_pipeline
from netapi.core.reflector import get_reflector
from netapi.learning.hub import get_learning_hub

# Import existing tools
try:
    from netapi.agent.tools import (
        tool_calc_or_convert,
        tool_memory_search,
        net_search,
        net_open,
        net_extract_answer
    )
except ImportError:
    # Fallback: Define minimal tools
    def tool_calc_or_convert(q: str) -> Optional[str]:
        import re
        match = re.search(r'(\d+)\s*\+\s*(\d+)', q)
        if match:
            a, b = int(match.group(1)), int(match.group(2))
            return f"{a+b}"
        return None
    
    def tool_memory_search(q: str, top_k: int = 3) -> tuple:
        return [], []
    
    def net_search(q: str, **kwargs):
        return []
    
    def net_open(url: str):
        return {}
    
    def net_extract_answer(text: str, q: str, **kwargs):
        return ""


router = APIRouter(prefix="/api/v2/chat", tags=["chat-v2"])


class ChatRequest(BaseModel):
    message: str
    persona: str = "helpful"
    lang: str = "de"
    enable_reflection: bool = True
    quality_threshold: float = 0.7
    conv_id: Optional[int] = None


class ChatResponse(BaseModel):
    ok: bool
    reply: str
    quality_score: Optional[float] = None
    confidence: Optional[float] = None
    retry_count: int = 0
    total_time_ms: int = 0
    tools_used: list = []
    sources: list = []
    trace: list = []
    conv_id: Optional[int] = None


# Global pipeline instance (created on first use)
_pipeline: Optional[ResponsePipeline] = None


def get_pipeline() -> ResponsePipeline:
    """Get or create global pipeline instance"""
    global _pipeline
    
    if _pipeline is None:
        # Import LLM (try real, fallback to mock)
        llm_backend = None
        try:
            from netapi.core import llm_local
            if llm_local and hasattr(llm_local, 'available') and llm_local.available():
                # Test if it actually works
                test = llm_local.chat_once("test", system="test")
                if test is not None:
                    llm_backend = llm_local
        except Exception:
            pass
        
        # Fallback to mock if real LLM unavailable
        if llm_backend is None:
            print("⚠️  Real LLM unavailable, using Mock LLM for development")
            try:
                from netapi.core import llm_mock
                llm_backend = llm_mock
            except ImportError:
                llm_backend = None
        
        # Define tool wrappers for pipeline
        def calc_tool(question: str) -> Optional[str]:
            result = tool_calc_or_convert(question)
            return result if result else None
        
        def memory_tool(question: str) -> Dict[str, Any]:
            hits, ids = tool_memory_search(question, top_k=3)
            return {
                "hits": hits,
                "memory_ids": ids,
            }
        
        def web_tool(question: str) -> Dict[str, Any]:
            # Search
            results = net_search(question, lang="de", max_results=3)
            if not results:
                return {}
            
            # Open first result
            first = results[0]
            page = net_open(first.get("url", ""))
            
            # Extract answer
            answer = net_extract_answer(
                page.get("text", ""),
                question,
                lang="de"
            )
            
            return {
                "answer": answer,
                "sources": [{"title": first.get("title"), "url": first.get("url")}]
            }
        
        tools = {
            "calc": calc_tool,
            "memory": memory_tool,
            "web": web_tool,
        }
        
        _pipeline = create_default_pipeline(llm_local, tools)
    
    return _pipeline


@router.post("", response_model=ChatResponse)
async def chat_v2(
    body: ChatRequest,
    request: Request,
    current = Depends(get_current_user_opt),
    db = Depends(get_db)
):
    """
    Clean chat endpoint with self-reflection.
    
    This endpoint:
    1. Abuse Guard Protection (NEW!)
    2. Uses the new ResponsePipeline
    3. Self-reflects on answers before sending
    4. Retries on low quality
    5. Logs everything for learning
    
    Example:
        POST /api/v2/chat
        {
            "message": "Was ist 2+2?",
            "persona": "helpful",
            "enable_reflection": true
        }
        
        Response:
        {
            "ok": true,
            "reply": "2+2 ist 4.",
            "quality_score": 0.95,
            "confidence": 0.9,
            "retry_count": 0,
            "total_time_ms": 234
        }
    """
    
    # Basic validation
    if not body.message or not body.message.strip():
        raise HTTPException(400, "Message cannot be empty")
    
    # Abuse Guard Protection (NEW!)
    try:
        from netapi.modules.security import get_abuse_guard
        abuse_guard = get_abuse_guard()
        
        user_id = current.get("id") if current else None
        check_result = await abuse_guard.check_prompt(body.message, user_id)
        
        if not check_result["allowed"]:
            raise HTTPException(
                403,
                {
                    "error": "Content policy violation",
                    "reason": check_result["reason"],
                    "severity": check_result["severity"]
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        # Don't block on abuse guard failure - log and continue
        print(f"⚠️ Abuse Guard check failed: {e}")
    
    # Get pipeline
    try:
        pipeline = get_pipeline()
    except Exception as e:
        raise HTTPException(500, f"Pipeline initialization failed: {e}")
    
    # Prepare user context
    user_context = {}
    if current:
        user_context["user_id"] = current.get("id")
        user_context["role"] = current.get("role")
        user_context["is_papa"] = current.get("is_papa", False)
    
    # Generate response through pipeline
    try:
        response = pipeline.generate(
            question=body.message,
            user_context=user_context,
            persona=body.persona,
            lang=body.lang
        )
    except Exception as e:
        raise HTTPException(500, f"Response generation failed: {e}")
    
    # Save to conversation if user logged in
    conv_id = None
    if current and current.get("id"):
        try:
            # Import conversation helpers from old router
            from .router import _ensure_conversation, _save_msg
            
            uid = int(current["id"])
            conv = _ensure_conversation(db, uid, body.conv_id)
            conv_id = conv.id
            
            _save_msg(db, conv.id, "user", body.message)
            _save_msg(db, conv.id, "ai", response.reply)
        except Exception as e:
            # Non-critical - just log
            print(f"Conversation save failed: {e}")
    
    # Build response
    return ChatResponse(
        ok=response.ok,
        reply=response.reply,
        quality_score=response.evaluation.overall_score if response.evaluation else None,
        confidence=response.evaluation.confidence if response.evaluation else None,
        retry_count=response.retry_count,
        total_time_ms=response.total_time_ms,
        tools_used=response.context.tools_used if response.context else [],
        sources=response.context.sources if response.context else [],
        trace=response.context.trace if response.context else [],
        conv_id=conv_id or body.conv_id
    )


@router.get("/ping")
def ping():
    """Health check"""
    return {"ok": True, "version": "2.0", "module": "chat-v2"}


@router.get("/stats")
def stats():
    """Get pipeline statistics including learning metrics"""
    try:
        pipeline = get_pipeline()
        reflector = get_reflector()
        learning_hub = get_learning_hub()
        
        return {
            "ok": True,
            "reflection": reflector.get_statistics(),
            "learning": learning_hub.get_statistics() if learning_hub else None,
            "mode": "mock_llm" if "llm_mock" in str(type(pipeline.llm)) else "real_llm"
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/feedback")
def add_feedback(
    interaction_id: str,
    feedback: str,  # "positive", "negative", "neutral"
    correction: Optional[str] = None
):
    """
    Add user feedback to improve learning.
    
    Example:
        POST /api/v2/chat/feedback
        {
            "interaction_id": "1729588800",
            "feedback": "positive"
        }
    """
    try:
        learning_hub = get_learning_hub()
        if not learning_hub:
            return {"ok": False, "error": "Learning Hub not available"}
        
        learning_hub.add_feedback(interaction_id, feedback, correction)
        return {"ok": True, "message": "Feedback recorded"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Export router
__all__ = ["router"]
