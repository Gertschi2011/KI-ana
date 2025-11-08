"""
Consensus Engine - Proof of Insight
Implements federated learning consensus
Phase 8 - Sub-Minds
"""
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from .node_registry import get_node_registry


class ProofOfInsight:
    """Implements Proof of Insight consensus algorithm"""
    
    def __init__(self):
        self.config = self._load_config()
        self.registry = get_node_registry()
        self.chain_file = Path("/home/kiana/ki_ana/data/knowledge_chain.json")
        self.chain = self._load_chain()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load submind config"""
        config_file = Path("/home/kiana/ki_ana/data/submind_config.json")
        
        if not config_file.exists():
            return {}
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def _load_chain(self) -> List[Dict[str, Any]]:
        """Load knowledge chain"""
        if not self.chain_file.exists():
            return []
        
        try:
            with open(self.chain_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def _save_chain(self):
        """Save knowledge chain"""
        self.chain_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.chain_file, 'w', encoding='utf-8') as f:
            json.dump(self.chain, f, indent=2)
    
    def propose_knowledge(
        self,
        proposer_node_id: str,
        knowledge: Dict[str, Any],
        trust_score: float
    ) -> Dict[str, Any]:
        """
        Node proposes new knowledge
        
        Args:
            proposer_node_id: ID of proposing node
            knowledge: Knowledge block to propose
            trust_score: Self-assessed trust score
        
        Returns:
            Proposal with validation status
        """
        # Score the proposal
        score = self._score_proposal(
            proposer_node_id,
            knowledge,
            trust_score
        )
        
        proposal = {
            "id": f"proposal_{int(time.time())}_{proposer_node_id}",
            "proposer": proposer_node_id,
            "knowledge": knowledge,
            "proposed_trust": trust_score,
            "calculated_score": score,
            "timestamp": int(time.time()),
            "status": "pending",
            "votes": {}
        }
        
        return proposal
    
    def _score_proposal(
        self,
        proposer_id: str,
        knowledge: Dict[str, Any],
        trust_score: float
    ) -> Dict[str, float]:
        """Score a knowledge proposal"""
        scoring = self.config.get('proof_of_insight', {}).get('scoring', {})
        
        # Get proposer's trust
        proposer = self.registry.get_node(proposer_id)
        proposer_trust = proposer.get('trust_score', 5.0) if proposer else 5.0
        
        scores = {
            "novelty": self._score_novelty(knowledge),
            "verification": trust_score / 10.0,  # Normalize to 0-1
            "usefulness": 0.5,  # Placeholder
            "source_quality": proposer_trust / 10.0
        }
        
        # Weighted sum
        total = sum(
            scores[k] * scoring.get(k, 0.25)
            for k in scores
        )
        
        scores["total"] = total
        
        return scores
    
    def _score_novelty(self, knowledge: Dict[str, Any]) -> float:
        """Score knowledge novelty (0-1)"""
        # Simple: check if similar knowledge exists in chain
        knowledge_hash = self._hash_knowledge(knowledge)
        
        # Check chain for similar
        similar_count = sum(
            1 for block in self.chain[-100:]  # Check last 100
            if self._hash_knowledge(block.get('knowledge', {})) == knowledge_hash
        )
        
        if similar_count == 0:
            return 1.0  # Completely novel
        elif similar_count == 1:
            return 0.5  # Somewhat similar
        else:
            return 0.1  # Already known
    
    def _hash_knowledge(self, knowledge: Dict[str, Any]) -> str:
        """Hash knowledge for similarity checking"""
        # Simple hash of title + content
        content = json.dumps(knowledge, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def vote_on_proposal(
        self,
        proposal_id: str,
        voter_node_id: str,
        vote: bool,
        confidence: float = 1.0
    ) -> Dict[str, Any]:
        """
        Node votes on a proposal
        
        Args:
            proposal_id: Proposal to vote on
            voter_node_id: Voting node
            vote: True=accept, False=reject
            confidence: Vote confidence (0-1)
        
        Returns:
            Vote result
        """
        voter = self.registry.get_node(voter_node_id)
        if not voter:
            return {"ok": False, "error": "Unknown voter"}
        
        vote_weight = voter.get('trust_score', 5.0) / 10.0  # Normalize to 0-1
        
        return {
            "voter": voter_node_id,
            "vote": vote,
            "confidence": confidence,
            "weight": vote_weight,
            "weighted_vote": vote_weight * confidence if vote else -vote_weight * confidence
        }
    
    def finalize_consensus(
        self,
        proposal: Dict[str, Any],
        votes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Finalize consensus on proposal
        
        Mother-node averages votes and signs if consensus reached
        """
        consensus_config = self.config.get('consensus_learning', {})
        quorum = consensus_config.get('quorum', 0.51)
        
        # Calculate weighted vote sum
        total_weight = sum(v['weight'] for v in votes)
        weighted_sum = sum(v['weighted_vote'] for v in votes)
        
        if total_weight == 0:
            consensus_reached = False
            final_trust = 0.0
        else:
            consensus_ratio = weighted_sum / total_weight
            consensus_reached = consensus_ratio >= quorum
            
            # Final trust is average of scores
            final_trust = (
                proposal['calculated_score']['total'] * 10 *
                (consensus_ratio if consensus_ratio > 0 else 0)
            )
        
        if consensus_reached:
            # Add to chain
            block = {
                "block_id": len(self.chain) + 1,
                "proposal_id": proposal['id'],
                "knowledge": proposal['knowledge'],
                "proposer": proposal['proposer'],
                "final_trust": round(final_trust, 2),
                "consensus_ratio": round(consensus_ratio, 3),
                "votes_count": len(votes),
                "timestamp": int(time.time()),
                "mother_signature": self._sign_block(proposal)
            }
            
            self.chain.append(block)
            self._save_chain()
            
            # Update proposer trust (reward)
            self.registry.update_trust_score(proposal['proposer'], +0.1)
        
        return {
            "consensus_reached": consensus_reached,
            "consensus_ratio": round(consensus_ratio, 3) if total_weight > 0 else 0,
            "final_trust": round(final_trust, 2),
            "block_added": consensus_reached
        }
    
    def _sign_block(self, proposal: Dict[str, Any]) -> str:
        """Mother-node signs the block"""
        # Simple signature (in production: use real cryptography)
        content = json.dumps(proposal, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def get_chain_stats(self) -> Dict[str, Any]:
        """Get knowledge chain statistics"""
        if not self.chain:
            return {
                "total_blocks": 0,
                "average_trust": 0,
                "latest_block": None
            }
        
        avg_trust = sum(b.get('final_trust', 0) for b in self.chain) / len(self.chain)
        
        return {
            "total_blocks": len(self.chain),
            "average_trust": round(avg_trust, 2),
            "latest_block": self.chain[-1] if self.chain else None,
            "chain_hash": hashlib.sha256(
                json.dumps(self.chain).encode()
            ).hexdigest()[:16]
        }


if __name__ == "__main__":
    # Test
    consensus = ProofOfInsight()
    
    # Propose knowledge
    knowledge = {
        "title": "New Pattern Found",
        "content": "Discovered correlation between X and Y"
    }
    
    proposal = consensus.propose_knowledge(
        proposer_node_id="child_vision_01",
        knowledge=knowledge,
        trust_score=7.5
    )
    
    print("Proposal:", json.dumps(proposal, indent=2))
    
    # Simulate votes
    votes = [
        consensus.vote_on_proposal(proposal['id'], "mother_node_main", True, 1.0),
        consensus.vote_on_proposal(proposal['id'], "child_language_01", True, 0.8)
    ]
    
    # Finalize
    result = consensus.finalize_consensus(proposal, votes)
    print("\nConsensus result:", json.dumps(result, indent=2))
    
    # Stats
    stats = consensus.get_chain_stats()
    print("\nChain stats:", json.dumps(stats, indent=2))
