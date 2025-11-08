"""
Confidence Scoring System

Evaluates confidence in answers and knowledge blocks.

Factors:
1. Source Quality - Trust score of sources
2. Confirmation Count - How many sources agree
3. Recency - How recent is the information
4. Completeness - Is the answer complete?
5. Certainty Language - Does the text express uncertainty?
"""
from __future__ import annotations
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import time


class ConfidenceScorer:
    """Calculate confidence scores for answers and knowledge."""
    
    def __init__(self):
        # Trust scores for sources (same as conflict resolver)
        self.source_trust = {
            "wikipedia.org": 0.9,
            "de.wikipedia.org": 0.9,
            "britannica.com": 0.85,
            "nature.com": 0.95,
            "science.org": 0.95,
            "gpt-5": 0.8,
            "gpt-4": 0.75,
            "user_input": 0.5,
            "web_crawl": 0.4,
            "default": 0.5
        }
        
        # Uncertainty language patterns
        self.uncertainty_patterns = [
            r'\b(vielleicht|möglicherweise|vermutlich|wahrscheinlich|eventuell)\b',
            r'\b(könnte|sollte|würde|dürfte)\b',
            r'\b(unsicher|unklar|fraglich|zweifelhaft)\b',
            r'\b(ich glaube|ich denke|ich vermute)\b',
            r'\b(possibly|maybe|perhaps|probably|likely)\b',
            r'\b(might|could|should|would)\b',
        ]
        
        # Certainty language patterns
        self.certainty_patterns = [
            r'\b(definitiv|sicher|gewiss|eindeutig|zweifellos)\b',
            r'\b(ist|sind|war|waren|wird|werden)\b',
            r'\b(nachweislich|bewiesenermaßen|wissenschaftlich belegt)\b',
            r'\b(definitely|certainly|surely|clearly|undoubtedly)\b',
        ]
    
    def score_answer(
        self,
        text: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate confidence score for an answer.
        
        Args:
            text: Answer text
            sources: List of sources used
            context: Additional context (topic, timestamp, etc.)
        
        Returns:
            Dict with confidence score and breakdown
        """
        scores = {}
        
        # 1. Source Quality (0-1)
        scores['source_quality'] = self._score_source_quality(sources or [])
        
        # 2. Confirmation Count (0-1)
        scores['confirmation'] = self._score_confirmation(sources or [])
        
        # 3. Language Certainty (0-1)
        scores['language_certainty'] = self._score_language_certainty(text)
        
        # 4. Completeness (0-1)
        scores['completeness'] = self._score_completeness(text)
        
        # 5. Recency (0-1) - if applicable
        scores['recency'] = self._score_recency(context or {})
        
        # Calculate weighted final score
        weights = {
            'source_quality': 0.3,
            'confirmation': 0.2,
            'language_certainty': 0.2,
            'completeness': 0.15,
            'recency': 0.15
        }
        
        final_score = sum(scores[k] * weights[k] for k in weights.keys())
        
        # Confidence level
        if final_score >= 0.8:
            level = "high"
        elif final_score >= 0.6:
            level = "medium"
        else:
            level = "low"
        
        return {
            "confidence_score": final_score,
            "confidence_level": level,
            "breakdown": scores,
            "weights": weights,
            "factors": self._explain_factors(scores, weights)
        }
    
    def _score_source_quality(self, sources: List[Dict[str, Any]]) -> float:
        """Score based on source quality."""
        if not sources:
            return 0.3  # Low confidence if no sources
        
        # Get trust scores for all sources
        trust_scores = []
        for source in sources:
            url = str(source.get('url', '')).lower()
            source_name = str(source.get('source', '')).lower()
            
            # Find matching trust score
            score = self.source_trust['default']
            for domain, trust in self.source_trust.items():
                if domain in url or domain in source_name:
                    score = trust
                    break
            
            trust_scores.append(score)
        
        # Average trust score
        return sum(trust_scores) / len(trust_scores) if trust_scores else 0.3
    
    def _score_confirmation(self, sources: List[Dict[str, Any]]) -> float:
        """Score based on number of confirming sources."""
        count = len(sources)
        
        if count == 0:
            return 0.2
        elif count == 1:
            return 0.5
        elif count == 2:
            return 0.7
        elif count >= 3:
            return min(1.0, 0.8 + (count - 3) * 0.05)
        
        return 0.5
    
    def _score_language_certainty(self, text: str) -> float:
        """Score based on certainty of language used."""
        text_lower = text.lower()
        
        # Count uncertainty markers
        uncertainty_count = 0
        for pattern in self.uncertainty_patterns:
            uncertainty_count += len(re.findall(pattern, text_lower))
        
        # Count certainty markers
        certainty_count = 0
        for pattern in self.certainty_patterns:
            certainty_count += len(re.findall(pattern, text_lower))
        
        # Calculate ratio
        total = uncertainty_count + certainty_count
        if total == 0:
            return 0.6  # Neutral if no markers
        
        certainty_ratio = certainty_count / total
        
        # Penalize high uncertainty
        if uncertainty_count > 5:
            return max(0.3, certainty_ratio * 0.8)
        
        return certainty_ratio
    
    def _score_completeness(self, text: str) -> float:
        """Score based on answer completeness."""
        # Simple heuristics
        word_count = len(text.split())
        
        if word_count < 10:
            return 0.3  # Too short, likely incomplete
        elif word_count < 30:
            return 0.6  # Brief but might be complete
        elif word_count < 100:
            return 0.8  # Good length
        elif word_count < 300:
            return 0.9  # Comprehensive
        else:
            return 0.85  # Very detailed (but might be verbose)
    
    def _score_recency(self, context: Dict[str, Any]) -> float:
        """Score based on information recency."""
        timestamp = context.get('timestamp')
        topic = str(context.get('topic', '')).lower()
        
        # Check if topic is time-sensitive
        time_sensitive_keywords = [
            'news', 'aktuell', 'current', 'heute', 'now',
            'preis', 'price', 'wetter', 'weather'
        ]
        
        is_time_sensitive = any(kw in topic for kw in time_sensitive_keywords)
        
        if not timestamp:
            # No timestamp - assume reasonably recent
            return 0.7 if not is_time_sensitive else 0.4
        
        # Calculate age in days
        try:
            if isinstance(timestamp, (int, float)):
                ts = float(timestamp)
            else:
                dt = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
                ts = dt.timestamp()
            
            age_days = (time.time() - ts) / 86400
            
            if is_time_sensitive:
                # For time-sensitive topics, recent is crucial
                if age_days < 1:
                    return 1.0
                elif age_days < 7:
                    return 0.8
                elif age_days < 30:
                    return 0.5
                else:
                    return 0.3
            else:
                # For general knowledge, age matters less
                if age_days < 365:
                    return 0.9
                elif age_days < 365 * 3:
                    return 0.8
                elif age_days < 365 * 5:
                    return 0.7
                else:
                    return 0.6
        except Exception:
            return 0.7
    
    def _explain_factors(self, scores: Dict[str, float], weights: Dict[str, float]) -> List[str]:
        """Generate human-readable explanations for score factors."""
        explanations = []
        
        for factor, score in scores.items():
            weight = weights.get(factor, 0)
            contribution = score * weight
            
            if contribution >= 0.15:
                level = "stark positiv"
            elif contribution >= 0.08:
                level = "positiv"
            elif contribution >= 0.04:
                level = "leicht positiv"
            else:
                level = "schwach"
            
            factor_names = {
                'source_quality': 'Quellen-Qualität',
                'confirmation': 'Bestätigung durch mehrere Quellen',
                'language_certainty': 'Sprachliche Sicherheit',
                'completeness': 'Vollständigkeit',
                'recency': 'Aktualität'
            }
            
            name = factor_names.get(factor, factor)
            explanations.append(f"{name}: {score:.2f} ({level})")
        
        return explanations
    
    def score_block(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate confidence score for a knowledge block."""
        text = str(block.get('content', ''))
        
        # Extract sources from block
        sources = []
        if block.get('url'):
            sources.append({'url': block['url'], 'source': block.get('source', '')})
        
        # Context
        context = {
            'timestamp': block.get('timestamp') or block.get('created_at'),
            'topic': block.get('topic', '')
        }
        
        return self.score_answer(text, sources, context)


# Global instance
_confidence_scorer = ConfidenceScorer()


def get_confidence_scorer() -> ConfidenceScorer:
    """Get global confidence scorer instance."""
    return _confidence_scorer
