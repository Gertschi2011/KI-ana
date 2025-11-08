"""
Conflict Resolution System

Automatically detects and resolves contradictions in knowledge blocks.

Strategies:
1. Source Trust Score - Prefer blocks from trusted sources
2. Recency - Prefer newer information (if appropriate)
3. Confirmation Count - Prefer information confirmed by multiple sources
4. LLM-based Resolution - Ask local LLM to decide when unclear
"""
from __future__ import annotations
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Conflict:
    """Represents a conflict between two blocks."""
    block_a_id: str
    block_b_id: str
    conflict_type: str  # "contradiction", "outdated", "inconsistency"
    topic: str
    detected_at: float
    confidence: float  # How confident are we this is a conflict? 0.0-1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_a_id": self.block_a_id,
            "block_b_id": self.block_b_id,
            "conflict_type": self.conflict_type,
            "topic": self.topic,
            "detected_at": self.detected_at,
            "confidence": self.confidence
        }


@dataclass
class Resolution:
    """Represents the resolution of a conflict."""
    conflict: Conflict
    winner_id: str
    loser_id: str
    reason: str
    resolved_at: float
    method: str  # "trust_score", "recency", "confirmation_count", "llm"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict": self.conflict.to_dict(),
            "winner_id": self.winner_id,
            "loser_id": self.loser_id,
            "reason": self.reason,
            "resolved_at": self.resolved_at,
            "method": self.method
        }


class ConflictResolver:
    """Detects and resolves conflicts in knowledge blocks."""
    
    def __init__(self):
        self.base_dir = Path.home() / "ki_ana"
        self.runtime_dir = self.base_dir / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        
        self.conflicts_file = self.runtime_dir / "conflicts.json"
        self.resolutions_file = self.runtime_dir / "resolutions.json"
        
        # Trust scores for sources (can be learned over time)
        self.source_trust = {
            "wikipedia.org": 0.9,
            "de.wikipedia.org": 0.9,
            "britannica.com": 0.85,
            "gpt-5": 0.8,
            "gpt-4": 0.75,
            "user_input": 0.5,
            "web_crawl": 0.4,
            "default": 0.5
        }
    
    def detect_conflicts_by_topic(self, topic: str, blocks: List[Dict[str, Any]]) -> List[Conflict]:
        """
        Detect conflicts in blocks about the same topic.
        
        Args:
            topic: Topic to check
            blocks: List of blocks to check for conflicts
            
        Returns:
            List of detected conflicts
        """
        conflicts = []
        
        # Simple conflict detection based on keywords
        # More sophisticated: use embeddings or LLM
        
        for i, block_a in enumerate(blocks):
            for block_b in blocks[i+1:]:
                conflict = self._check_block_pair(block_a, block_b, topic)
                if conflict:
                    conflicts.append(conflict)
        
        return conflicts
    
    def _check_block_pair(self, block_a: Dict[str, Any], block_b: Dict[str, Any], topic: str) -> Optional[Conflict]:
        """Check if two blocks contradict each other."""
        content_a = str(block_a.get("content", "")).lower()
        content_b = str(block_b.get("content", "")).lower()
        
        # Simple contradiction detection patterns
        contradictions = [
            # Temporal contradictions
            (r"(\d{4})", r"(\d{4})"),  # Different years
            # Negation patterns
            ("ist", "ist nicht"),
            ("war", "war nicht"),
            ("wird", "wird nicht"),
            ("kann", "kann nicht"),
            ("hat", "hat nicht"),
            # Quantity contradictions
            ("mehr", "weniger"),
            ("größer", "kleiner"),
            ("höher", "niedriger"),
        ]
        
        # Check for negation patterns
        has_conflict = False
        confidence = 0.0
        conflict_type = "inconsistency"
        
        # Check if one contains affirmation and other negation
        for pos, neg in contradictions:
            if pos in content_a and neg in content_b:
                has_conflict = True
                confidence = 0.7
                conflict_type = "contradiction"
                break
            elif neg in content_a and pos in content_b:
                has_conflict = True
                confidence = 0.7
                conflict_type = "contradiction"
                break
        
        # Check for temporal conflicts (different dates for same event)
        if not has_conflict:  # Only check if no contradiction found yet
            import re
            years_a = re.findall(r'\b(19|20)\d{2}\b', content_a)
            years_b = re.findall(r'\b(19|20)\d{2}\b', content_b)
            
            if years_a and years_b:
                # If both mention years and they're different (potential conflict)
                years_a_set = set(years_a)
                years_b_set = set(years_b)
                
                # Check if they have different years (no overlap)
                if len(years_a_set & years_b_set) == 0 and years_a_set != years_b_set:
                    # Both mention years but different ones - likely a conflict
                    has_conflict = True
                    confidence = 0.6
                    conflict_type = "temporal_conflict"
        
        if has_conflict:
            return Conflict(
                block_a_id=block_a.get("id", ""),
                block_b_id=block_b.get("id", ""),
                conflict_type=conflict_type,
                topic=topic,
                detected_at=time.time(),
                confidence=confidence
            )
        
        return None
    
    def resolve_conflict(self, conflict: Conflict, block_a: Dict[str, Any], block_b: Dict[str, Any]) -> Resolution:
        """
        Resolve a conflict between two blocks.
        
        Priority:
        1. Trust Score of source
        2. Recency (if applicable)
        3. Confirmation count (how many other blocks agree)
        4. LLM decision (if needed)
        """
        
        # Strategy 1: Trust Score
        trust_a = self._get_trust_score(block_a)
        trust_b = self._get_trust_score(block_b)
        
        if abs(trust_a - trust_b) > 0.2:  # Significant difference
            if trust_a > trust_b:
                return Resolution(
                    conflict=conflict,
                    winner_id=conflict.block_a_id,
                    loser_id=conflict.block_b_id,
                    reason=f"Higher trust score: {trust_a:.2f} vs {trust_b:.2f}",
                    resolved_at=time.time(),
                    method="trust_score"
                )
            else:
                return Resolution(
                    conflict=conflict,
                    winner_id=conflict.block_b_id,
                    loser_id=conflict.block_a_id,
                    reason=f"Higher trust score: {trust_b:.2f} vs {trust_a:.2f}",
                    resolved_at=time.time(),
                    method="trust_score"
                )
        
        # Strategy 2: Recency (for time-sensitive information)
        timestamp_a = self._get_timestamp(block_a)
        timestamp_b = self._get_timestamp(block_b)
        
        if timestamp_a and timestamp_b:
            # Prefer newer if topic is likely time-sensitive
            if self._is_time_sensitive_topic(conflict.topic):
                if timestamp_a > timestamp_b:
                    return Resolution(
                        conflict=conflict,
                        winner_id=conflict.block_a_id,
                        loser_id=conflict.block_b_id,
                        reason=f"More recent information",
                        resolved_at=time.time(),
                        method="recency"
                    )
                else:
                    return Resolution(
                        conflict=conflict,
                        winner_id=conflict.block_b_id,
                        loser_id=conflict.block_a_id,
                        reason=f"More recent information",
                        resolved_at=time.time(),
                        method="recency"
                    )
        
        # Strategy 3: Default to block A (needs LLM in future)
        return Resolution(
            conflict=conflict,
            winner_id=conflict.block_a_id,
            loser_id=conflict.block_b_id,
            reason="Default resolution - manual review recommended",
            resolved_at=time.time(),
            method="default"
        )
    
    def _get_trust_score(self, block: Dict[str, Any]) -> float:
        """Get trust score for a block based on its source."""
        source = str(block.get("source", "default")).lower()
        url = str(block.get("url", "")).lower()
        
        # Check URL for known domains
        for domain, score in self.source_trust.items():
            if domain in url or domain in source:
                return score
        
        # Check source field
        for source_name, score in self.source_trust.items():
            if source_name in source:
                return score
        
        return self.source_trust["default"]
    
    def _get_timestamp(self, block: Dict[str, Any]) -> Optional[float]:
        """Extract timestamp from block."""
        # Try various timestamp fields
        for field in ["timestamp", "created_at", "ts"]:
            if field in block:
                ts_str = block[field]
                if isinstance(ts_str, (int, float)):
                    return float(ts_str)
                elif isinstance(ts_str, str):
                    # Try parsing ISO format
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        return dt.timestamp()
                    except Exception:
                        pass
        return None
    
    def _is_time_sensitive_topic(self, topic: str) -> bool:
        """Check if topic is time-sensitive."""
        time_sensitive_keywords = [
            "news", "aktuell", "heute", "current", "now",
            "preis", "price", "wetter", "weather",
            "politik", "politics", "corona", "covid"
        ]
        topic_lower = topic.lower()
        return any(kw in topic_lower for kw in time_sensitive_keywords)
    
    def apply_resolution(self, resolution: Resolution) -> Dict[str, Any]:
        """
        Apply a resolution (archive loser, mark winner).
        
        Returns:
            Dict with action details
        """
        # This would interact with memory_store to:
        # 1. Move loser block to archive/trash
        # 2. Add metadata to winner about conflict resolution
        
        result = {
            "ok": True,
            "action": "resolution_applied",
            "winner_id": resolution.winner_id,
            "loser_id": resolution.loser_id,
            "method": resolution.method,
            "timestamp": resolution.resolved_at
        }
        
        # Save resolution to file
        self._save_resolution(resolution)
        
        return result
    
    def _save_resolution(self, resolution: Resolution) -> None:
        """Save resolution to disk."""
        try:
            # Load existing resolutions
            resolutions = []
            if self.resolutions_file.exists():
                resolutions = json.loads(self.resolutions_file.read_text())
            
            # Add new resolution
            resolutions.append(resolution.to_dict())
            
            # Keep last 1000
            resolutions = resolutions[-1000:]
            
            # Save
            self.resolutions_file.write_text(json.dumps(resolutions, indent=2))
        except Exception:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get conflict resolution statistics."""
        try:
            resolutions = []
            if self.resolutions_file.exists():
                resolutions = json.loads(self.resolutions_file.read_text())
            
            total = len(resolutions)
            by_method = {}
            by_type = {}
            
            for res in resolutions:
                method = res.get("method", "unknown")
                by_method[method] = by_method.get(method, 0) + 1
                
                conflict_type = res.get("conflict", {}).get("conflict_type", "unknown")
                by_type[conflict_type] = by_type.get(conflict_type, 0) + 1
            
            return {
                "total_resolutions": total,
                "by_method": by_method,
                "by_type": by_type,
                "last_resolution": resolutions[-1] if resolutions else None
            }
        except Exception:
            return {
                "total_resolutions": 0,
                "by_method": {},
                "by_type": {},
                "last_resolution": None
            }


# Global instance
_conflict_resolver = ConflictResolver()


def get_conflict_resolver() -> ConflictResolver:
    """Get global conflict resolver instance."""
    return _conflict_resolver
