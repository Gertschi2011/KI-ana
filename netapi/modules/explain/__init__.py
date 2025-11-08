"""
Explain Module - Response Explanation System

Provides "Why did I answer this way?" explanations for all AI responses.

Features:
- Source tracking with trust scores
- Reasoning step recording
- Tool/Skill usage tracking
- SubMind contribution tracking
- Knowledge block references
- Confidence score calculation
- Full audit trail

Usage:
    from netapi.modules.explain import get_explainer, get_enricher
    
    # For manual tracking:
    explainer = get_explainer()
    exp = explainer.create_explanation(...)
    
    # For automatic chat enrichment:
    enricher = get_enricher()
    response_id = enricher.start_explanation(query)
    enricher.add_source(...)
    explanation = enricher.finalize(response_id, response_text)
"""

from .explainer import (
    ResponseExplainer,
    ResponseExplanation,
    ExplanationSource,
    ExplanationStep,
    ExplanationContext,
    get_explainer
)

from .middleware import (
    ExplanationEnricher,
    get_enricher,
    with_explanation
)

__all__ = [
    # Core classes
    "ResponseExplainer",
    "ResponseExplanation",
    "ExplanationSource",
    "ExplanationStep",
    "ExplanationContext",
    
    # Middleware
    "ExplanationEnricher",
    
    # Factory functions
    "get_explainer",
    "get_enricher",
    
    # Decorators
    "with_explanation",
]
