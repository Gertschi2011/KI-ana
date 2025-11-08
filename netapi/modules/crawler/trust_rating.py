"""
Trust & Source Rating System

Evaluates source trustworthiness and content quality for crawled data.
Implements Proof-of-Source and scoring heuristics.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from urllib.parse import urlparse
import re
from loguru import logger


class TrustRating:
    """
    Source Trust Rating System
    
    Evaluates:
    - Domain reputation
    - Content quality
    - Source reliability
    - Freshness
    - Citations/references
    """
    
    def __init__(self):
        self.trusted_domains = self._load_trusted_domains()
        self.suspicious_patterns = self._load_suspicious_patterns()
        self.quality_indicators = self._load_quality_indicators()
        
    def _load_trusted_domains(self) -> Dict[str, float]:
        """Load trusted domain list with base scores"""
        return {
            # Academic & Official
            "wikipedia.org": 0.85,
            "arxiv.org": 0.95,
            "github.com": 0.80,
            "stackoverflow.com": 0.85,
            "gov": 0.90,  # All .gov domains
            "edu": 0.85,  # All .edu domains
            
            # News (German)
            "tagesschau.de": 0.85,
            "zeit.de": 0.85,
            "faz.net": 0.80,
            "sueddeutsche.de": 0.80,
            "spiegel.de": 0.75,
            
            # Tech
            "techcrunch.com": 0.75,
            "theverge.com": 0.75,
            "arstechnica.com": 0.80,
            
            # Documentation
            "python.org": 0.90,
            "docs.python.org": 0.95,
            "nodejs.org": 0.90,
            "mozilla.org": 0.85,
        }
    
    def _load_suspicious_patterns(self) -> List[str]:
        """Load patterns indicating low-quality content"""
        return [
            r"(?i)(clickbait|sensational|shocking|you won't believe)",
            r"(?i)(buy now|limited offer|act fast)",
            r"(?i)(crypto scam|get rich quick|miracle cure)",
            r"\b[A-Z]{3,}\b.*\b[A-Z]{3,}\b",  # Excessive caps
            r"!!+",  # Multiple exclamation marks
        ]
    
    def _load_quality_indicators(self) -> List[str]:
        """Load patterns indicating high-quality content"""
        return [
            r"(?i)(study shows|research|according to|published in)",
            r"(?i)(citation|reference|source|bibliography)",
            r"\[\d+\]",  # Citation markers [1], [2]
            r"doi:",  # DOI references
            r"ISSN|ISBN",  # Journal/Book identifiers
        ]
    
    def rate_source(
        self,
        url: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Rate source trustworthiness
        
        Returns:
            {
                "trust_score": float (0-100),
                "quality_score": float (0-100),
                "overall_score": float (0-100),
                "factors": {...},
                "proof_of_source": {...}
            }
        """
        
        factors = {}
        
        # 1. Domain reputation
        domain_score = self._rate_domain(url)
        factors["domain_reputation"] = domain_score
        
        # 2. Content quality
        quality_score = self._rate_content_quality(content)
        factors["content_quality"] = quality_score
        
        # 3. Freshness
        freshness_score = self._rate_freshness(metadata)
        factors["freshness"] = freshness_score
        
        # 4. Citation quality
        citation_score = self._rate_citations(content)
        factors["citations"] = citation_score
        
        # 5. Suspicious content check
        suspicion_penalty = self._check_suspicious(content)
        factors["suspicion_penalty"] = suspicion_penalty
        
        # Calculate overall scores
        trust_score = (
            domain_score * 0.4 +
            citation_score * 0.3 +
            freshness_score * 0.2 +
            (100 - suspicion_penalty) * 0.1
        )
        
        overall_score = (
            trust_score * 0.6 +
            quality_score * 0.4
        )
        
        # Proof of Source
        proof_of_source = self._generate_proof(url, metadata)
        
        return {
            "trust_score": round(trust_score, 2),
            "quality_score": round(quality_score, 2),
            "overall_score": round(overall_score, 2),
            "factors": factors,
            "proof_of_source": proof_of_source,
            "rating": self._get_rating_label(overall_score)
        }
    
    def _rate_domain(self, url: str) -> float:
        """Rate domain reputation (0-100)"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Check exact matches
            for trusted_domain, score in self.trusted_domains.items():
                if domain.endswith(trusted_domain):
                    return score * 100
            
            # Check TLD-based trust
            if domain.endswith('.gov'):
                return 90.0
            elif domain.endswith('.edu'):
                return 85.0
            elif domain.endswith('.org'):
                return 70.0
            elif domain.endswith(('.com', '.net')):
                return 50.0
            else:
                return 40.0
                
        except Exception as e:
            logger.warning(f"Domain rating failed: {e}")
            return 40.0
    
    def _rate_content_quality(self, content: str) -> float:
        """Rate content quality (0-100)"""
        if not content:
            return 0.0
        
        score = 50.0  # Base score
        
        # Length check (longer = more detailed)
        length = len(content)
        if length > 5000:
            score += 15
        elif length > 2000:
            score += 10
        elif length > 500:
            score += 5
        
        # Quality indicators
        quality_count = sum(
            1 for pattern in self.quality_indicators
            if re.search(pattern, content)
        )
        score += min(quality_count * 5, 20)
        
        # Structure (paragraphs, headings)
        if '\n\n' in content:  # Has paragraphs
            score += 5
        if re.search(r'#{1,6}\s', content):  # Has markdown headings
            score += 5
        
        return min(score, 100.0)
    
    def _rate_freshness(self, metadata: Optional[Dict[str, Any]]) -> float:
        """Rate content freshness (0-100)"""
        if not metadata or 'published_date' not in metadata:
            return 50.0  # Unknown = neutral
        
        try:
            pub_date = datetime.fromisoformat(metadata['published_date'])
            age_days = (datetime.now() - pub_date).days
            
            # Scoring by age
            if age_days < 30:
                return 100.0
            elif age_days < 90:
                return 90.0
            elif age_days < 180:
                return 80.0
            elif age_days < 365:
                return 70.0
            elif age_days < 730:
                return 60.0
            else:
                return 40.0
                
        except Exception as e:
            logger.warning(f"Freshness rating failed: {e}")
            return 50.0
    
    def _rate_citations(self, content: str) -> float:
        """Rate citation quality (0-100)"""
        if not content:
            return 0.0
        
        score = 40.0  # Base score
        
        # Count citation markers
        citation_markers = len(re.findall(r'\[\d+\]', content))
        score += min(citation_markers * 5, 30)
        
        # Check for bibliography/references section
        if re.search(r'(?i)(references|bibliography|citations)', content):
            score += 20
        
        # Check for DOI
        if re.search(r'doi:', content):
            score += 10
        
        return min(score, 100.0)
    
    def _check_suspicious(self, content: str) -> float:
        """Check for suspicious content (0-100 penalty)"""
        if not content:
            return 0.0
        
        penalty = 0.0
        
        for pattern in self.suspicious_patterns:
            if re.search(pattern, content):
                penalty += 20
        
        return min(penalty, 100.0)
    
    def _generate_proof(self, url: str, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate Proof-of-Source metadata"""
        return {
            "url": url,
            "domain": urlparse(url).netloc,
            "crawled_at": datetime.now().isoformat(),
            "metadata": metadata or {},
            "verification": {
                "domain_verified": True,
                "ssl_verified": url.startswith('https://'),
                "timestamp": datetime.now().isoformat()
            }
        }
    
    def _get_rating_label(self, score: float) -> str:
        """Get human-readable rating label"""
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "Very Good"
        elif score >= 70:
            return "Good"
        elif score >= 60:
            return "Fair"
        elif score >= 50:
            return "Moderate"
        else:
            return "Low"


# Singleton
_trust_rating_instance = None


def get_trust_rating() -> TrustRating:
    """Get or create trust rating singleton"""
    global _trust_rating_instance
    
    if _trust_rating_instance is None:
        _trust_rating_instance = TrustRating()
    
    return _trust_rating_instance
