"""
Block Voting System für KI_ana

Features:
- Block-Voting für Vertrauensbewertungen
- Trust-Score Calculation
- Vote Aggregation
- Reputation System
"""
from __future__ import annotations
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
import sys
from pathlib import Path

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))


@dataclass
class Vote:
    """Vote for a block."""
    vote_id: str
    block_id: str
    voter_id: str
    vote_value: int  # -1 (downvote), 0 (neutral), 1 (upvote)
    timestamp: float
    reason: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TrustScore:
    """Trust score for a device."""
    device_id: str
    score: float  # 0.0 - 1.0
    votes_cast: int
    votes_received: int
    reputation: float
    
    def to_dict(self) -> Dict:
        return asdict(self)


class VotingSystem:
    """
    Voting System for Block Trust.
    
    Singleton pattern.
    """
    
    _instance: Optional['VotingSystem'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Device ID
        from submind_manager import get_submind_manager
        self.device_id = get_submind_manager().this_device_id
        
        # Votes storage
        self.votes: Dict[str, List[Vote]] = defaultdict(list)  # block_id -> votes
        
        # Trust scores
        self.trust_scores: Dict[str, TrustScore] = {}
        
        # Vote history
        self.vote_history: List[Vote] = []
        
        print(f"✅ Voting System initialized")
    
    def cast_vote(self, block_id: str, vote_value: int, reason: str = None) -> Vote:
        """
        Cast a vote for a block.
        
        Args:
            block_id: Block to vote on
            vote_value: -1 (downvote), 0 (neutral), 1 (upvote)
            reason: Optional reason for vote
        """
        # Validate vote value
        if vote_value not in [-1, 0, 1]:
            raise ValueError("Vote value must be -1, 0, or 1")
        
        # Check if already voted
        existing_votes = [v for v in self.votes[block_id] if v.voter_id == self.device_id]
        if existing_votes:
            print(f"⚠️  Already voted on block {block_id}, updating vote")
            # Remove old vote
            self.votes[block_id] = [v for v in self.votes[block_id] if v.voter_id != self.device_id]
        
        # Create vote
        vote = Vote(
            vote_id=f"vote_{int(time.time())}_{self.device_id}",
            block_id=block_id,
            voter_id=self.device_id,
            vote_value=vote_value,
            timestamp=time.time(),
            reason=reason
        )
        
        # Store vote
        self.votes[block_id].append(vote)
        self.vote_history.append(vote)
        
        # Update trust scores
        self._update_trust_scores(block_id)
        
        print(f"✅ Vote cast: {vote_value} for block {block_id[:8]}...")
        
        return vote
    
    def get_block_votes(self, block_id: str) -> List[Vote]:
        """Get all votes for a block."""
        return self.votes.get(block_id, [])
    
    def get_block_score(self, block_id: str) -> Dict:
        """Get aggregated score for a block."""
        votes = self.get_block_votes(block_id)
        
        if not votes:
            return {
                "block_id": block_id,
                "total_votes": 0,
                "upvotes": 0,
                "downvotes": 0,
                "neutral": 0,
                "score": 0.0,
                "trust_weighted_score": 0.0
            }
        
        upvotes = sum(1 for v in votes if v.vote_value == 1)
        downvotes = sum(1 for v in votes if v.vote_value == -1)
        neutral = sum(1 for v in votes if v.vote_value == 0)
        
        # Simple score
        total = len(votes)
        score = (upvotes - downvotes) / total if total > 0 else 0.0
        
        # Trust-weighted score
        weighted_sum = 0.0
        weight_total = 0.0
        
        for vote in votes:
            trust = self.get_trust_score(vote.voter_id)
            weight = trust.score if trust else 0.5
            weighted_sum += vote.vote_value * weight
            weight_total += weight
        
        trust_weighted_score = weighted_sum / weight_total if weight_total > 0 else 0.0
        
        return {
            "block_id": block_id,
            "total_votes": total,
            "upvotes": upvotes,
            "downvotes": downvotes,
            "neutral": neutral,
            "score": score,
            "trust_weighted_score": trust_weighted_score
        }
    
    def _update_trust_scores(self, block_id: str):
        """Update trust scores based on voting patterns."""
        # Get block creator
        try:
            from block_sync import get_block_sync_manager
            block = get_block_sync_manager().get_block(block_id)
            if not block:
                return
            
            creator_id = block.device_id
            
            # Update creator's trust score
            if creator_id not in self.trust_scores:
                self.trust_scores[creator_id] = TrustScore(
                    device_id=creator_id,
                    score=0.5,
                    votes_cast=0,
                    votes_received=0,
                    reputation=0.5
                )
            
            creator_score = self.trust_scores[creator_id]
            
            # Get votes for this block
            votes = self.get_block_votes(block_id)
            creator_score.votes_received = len(votes)
            
            # Calculate new score based on votes
            if votes:
                upvotes = sum(1 for v in votes if v.vote_value == 1)
                downvotes = sum(1 for v in votes if v.vote_value == -1)
                
                # Update score (moving average)
                vote_ratio = (upvotes - downvotes) / len(votes)
                creator_score.score = 0.8 * creator_score.score + 0.2 * ((vote_ratio + 1) / 2)
                creator_score.score = max(0.0, min(1.0, creator_score.score))
                
                # Update reputation
                creator_score.reputation = creator_score.score
        
        except Exception as e:
            print(f"⚠️  Error updating trust scores: {e}")
    
    def get_trust_score(self, device_id: str) -> Optional[TrustScore]:
        """Get trust score for a device."""
        return self.trust_scores.get(device_id)
    
    def get_top_trusted_devices(self, limit: int = 10) -> List[TrustScore]:
        """Get top trusted devices."""
        scores = sorted(
            self.trust_scores.values(),
            key=lambda x: x.score,
            reverse=True
        )
        return scores[:limit]
    
    def get_voting_stats(self) -> Dict:
        """Get voting statistics."""
        return {
            "total_votes": len(self.vote_history),
            "blocks_voted_on": len(self.votes),
            "devices_with_trust_scores": len(self.trust_scores),
            "average_trust_score": sum(s.score for s in self.trust_scores.values()) / len(self.trust_scores) if self.trust_scores else 0.0
        }


# Singleton
_system: Optional[VotingSystem] = None


def get_voting_system() -> VotingSystem:
    """Get singleton voting system."""
    global _system
    if _system is None:
        _system = VotingSystem()
    return _system


if __name__ == "__main__":
    print("🗳️  Voting System Test\n")
    
    system = get_voting_system()
    
    # Simulate votes
    print("1️⃣ Casting votes...")
    system.cast_vote("block-123", 1, "Good content")
    system.cast_vote("block-123", 1, "Helpful")
    system.cast_vote("block-123", -1, "Inaccurate")
    
    # Get block score
    print("\n2️⃣ Block score:")
    score = system.get_block_score("block-123")
    print(f"   Total votes: {score['total_votes']}")
    print(f"   Upvotes: {score['upvotes']}")
    print(f"   Downvotes: {score['downvotes']}")
    print(f"   Score: {score['score']:.2f}")
    print(f"   Trust-weighted: {score['trust_weighted_score']:.2f}")
    
    # Stats
    print("\n3️⃣ Voting stats:")
    stats = system.get_voting_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n✅ Voting System test complete!")
