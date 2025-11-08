"""
Explanation Middleware

Automatically enriches chat responses with explanations.
"""
from typing import Dict, Any, Optional
import time
import hashlib
from .explainer import get_explainer, ExplanationContext


class ExplanationEnricher:
    """
    Enriches AI responses with explanation data.
    
    Usage in chat endpoint:
        enricher = ExplanationEnricher()
        
        # Before generating response
        response_id = enricher.start_explanation(query)
        
        # During processing
        enricher.add_source(response_id, ...)
        enricher.add_step(response_id, ...)
        
        # After response generated
        explanation = enricher.finalize(response_id, response_text)
        
        # Return both response and explanation
        return {
            "response": response_text,
            "explanation": explanation
        }
    """
    
    def __init__(self):
        self.explainer = get_explainer()
        self.active_explanations: Dict[str, float] = {}
    
    def generate_response_id(self, query: str) -> str:
        """Generate unique response ID"""
        timestamp = str(time.time())
        combined = f"{query[:100]}_{timestamp}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]
    
    def start_explanation(
        self,
        query: str,
        model_used: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Start tracking an explanation.
        
        Returns: response_id for tracking
        """
        response_id = self.generate_response_id(query)
        self.active_explanations[response_id] = time.time()
        
        # Create placeholder explanation
        self.explainer.create_explanation(
            response_id=response_id,
            query=query,
            response="",  # Will be updated later
            model_used=model_used,
            temperature=temperature
        )
        
        return response_id
    
    def add_source(
        self,
        response_id: str,
        source_id: str,
        source_type: str,
        content_snippet: str,
        trust_score: float = 0.0,
        url: Optional[str] = None
    ):
        """Add a source to the explanation"""
        self.explainer.add_source(
            response_id,
            source_id,
            source_type,
            content_snippet,
            trust_score,
            url
        )
    
    def add_step(
        self,
        response_id: str,
        action: str,
        description: str,
        result: Optional[str] = None
    ):
        """Add a reasoning step"""
        self.explainer.add_reasoning_step(
            response_id,
            action,
            description,
            result
        )
    
    def add_tool(
        self,
        response_id: str,
        tool_name: str,
        tool_input: Any,
        tool_output: Any
    ):
        """Add tool usage"""
        self.explainer.add_tool_usage(
            response_id,
            tool_name,
            tool_input,
            tool_output
        )
    
    def add_submind(
        self,
        response_id: str,
        submind_id: str,
        contribution_type: str,
        data: Any
    ):
        """Add SubMind contribution"""
        self.explainer.add_submind_contribution(
            response_id,
            submind_id,
            contribution_type,
            data
        )
    
    def add_knowledge_block(self, response_id: str, block_index: int):
        """Add knowledge block reference"""
        self.explainer.add_knowledge_block(response_id, block_index)
    
    def finalize(
        self,
        response_id: str,
        response_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Finalize explanation and return it.
        
        Returns: explanation dict or None if not found
        """
        if response_id not in self.active_explanations:
            return None
        
        start_time = self.active_explanations.pop(response_id)
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Update response text
        exp = self.explainer.get_explanation(response_id)
        if exp:
            exp.response = response_text
        
        # Finalize
        self.explainer.finalize_explanation(response_id, duration_ms)
        
        # Get and save
        exp = self.explainer.get_explanation(response_id)
        if exp:
            self.explainer.save_explanation(exp)
            return exp.to_dict()
        
        return None
    
    def get_compact_explanation(self, response_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a compact version of the explanation for inline display.
        
        Returns only essential info: sources count, confidence, top source.
        """
        exp = self.explainer.get_explanation(response_id)
        if not exp:
            return None
        
        # Get top source by trust score
        top_source = None
        if exp.sources:
            top_source = max(exp.sources, key=lambda s: s.trust_score)
        
        return {
            "response_id": response_id,
            "confidence_score": exp.confidence_score,
            "sources_count": len(exp.sources),
            "top_source": {
                "source_id": top_source.source_id,
                "source_type": top_source.source_type,
                "trust_score": top_source.trust_score
            } if top_source else None,
            "reasoning_steps_count": len(exp.reasoning_steps),
            "tools_used_count": len(exp.tools_used),
            "knowledge_blocks_count": len(exp.knowledge_blocks)
        }


# Global instance
_enricher_instance: Optional[ExplanationEnricher] = None


def get_enricher() -> ExplanationEnricher:
    """Get or create global ExplanationEnricher instance"""
    global _enricher_instance
    if _enricher_instance is None:
        _enricher_instance = ExplanationEnricher()
    return _enricher_instance


# Helper decorator for chat endpoints
def with_explanation(func):
    """
    Decorator that automatically adds explanation tracking to a function.
    
    Usage:
        @with_explanation
        async def generate_response(query: str, ...) -> Dict[str, Any]:
            # Your existing code
            return {"response": response_text}
    
    The decorated function will receive an additional 'explainer' parameter
    and should return a dict with 'response' key. The decorator adds 'explanation'.
    """
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        enricher = get_enricher()
        
        # Extract query from args/kwargs
        query = kwargs.get('query') or (args[0] if args else "")
        
        # Start explanation
        response_id = enricher.start_explanation(query)
        
        # Add explainer to kwargs
        kwargs['explainer'] = enricher
        kwargs['response_id'] = response_id
        
        # Call original function
        result = await func(*args, **kwargs)
        
        # Finalize explanation
        if isinstance(result, dict) and 'response' in result:
            explanation = enricher.finalize(response_id, result['response'])
            result['explanation'] = explanation
            result['explanation_id'] = response_id
        
        return result
    
    return wrapper


if __name__ == "__main__":
    # Self-test
    print("=== Explanation Enricher Self-Test ===\n")
    
    enricher = ExplanationEnricher()
    
    # Start explanation
    response_id = enricher.start_explanation(
        query="What is Python?",
        model_used="llama3.2"
    )
    print(f"Response ID: {response_id}")
    
    # Add sources
    enricher.add_source(
        response_id,
        source_id="block_42",
        source_type="knowledge_block",
        content_snippet="Python is a programming language",
        trust_score=0.95
    )
    
    # Add steps
    enricher.add_step(
        response_id,
        action="search",
        description="Searched knowledge base"
    )
    
    # Finalize
    explanation = enricher.finalize(
        response_id,
        response_text="Python is a high-level programming language."
    )
    
    if explanation:
        print(f"Confidence: {explanation['confidence_score']:.2f}")
        print(f"Sources: {len(explanation['sources'])}")
        print(f"Steps: {len(explanation['reasoning_steps'])}")
        
        # Get compact version
        compact = enricher.get_compact_explanation(response_id)
        if compact:
            print(f"\nCompact Explanation:")
            print(f"  Confidence: {compact['confidence_score']:.2f}")
            print(f"  Sources: {compact['sources_count']}")
    
    print("\n✅ Explanation Enricher functional!")
