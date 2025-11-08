"""
Response Explainer - Makes AI reasoning transparent

Tracks and explains:
- Sources used (with trust scores)
- Skills/Tools invoked
- Knowledge blocks referenced
- SubMind contributions
- Reasoning path
"""
from __future__ import annotations
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import json
import hashlib


@dataclass
class ExplanationSource:
    """A source used in generating the response"""
    source_id: str
    source_type: str  # "knowledge_block", "web", "memory", "tool", "llm"
    content_snippet: str
    trust_score: float = 0.0
    timestamp: Optional[float] = None
    url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExplanationStep:
    """A step in the reasoning process"""
    step_number: int
    action: str
    description: str
    result: Optional[str] = None
    duration_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResponseExplanation:
    """Complete explanation for an AI response"""
    response_id: str
    query: str
    response: str
    
    # Sources
    sources: List[ExplanationSource] = field(default_factory=list)
    
    # Reasoning steps
    reasoning_steps: List[ExplanationStep] = field(default_factory=list)
    
    # Tools/Skills used
    tools_used: List[Dict[str, Any]] = field(default_factory=list)
    
    # SubMind contributions
    submind_contributions: Dict[str, Any] = field(default_factory=dict)
    
    # Knowledge blocks referenced
    knowledge_blocks: List[int] = field(default_factory=list)
    
    # Confidence & Trust
    confidence_score: float = 0.0
    avg_trust_score: float = 0.0
    
    # Context
    model_used: Optional[str] = None
    temperature: Optional[float] = None
    
    # Timing
    created_at: float = field(default_factory=time.time)
    total_duration_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_id": self.response_id,
            "query": self.query,
            "response": self.response,
            "sources": [
                {
                    "source_id": s.source_id,
                    "source_type": s.source_type,
                    "content_snippet": s.content_snippet,
                    "trust_score": s.trust_score,
                    "timestamp": s.timestamp,
                    "url": s.url,
                    "metadata": s.metadata
                }
                for s in self.sources
            ],
            "reasoning_steps": [
                {
                    "step_number": step.step_number,
                    "action": step.action,
                    "description": step.description,
                    "result": step.result,
                    "duration_ms": step.duration_ms,
                    "metadata": step.metadata
                }
                for step in self.reasoning_steps
            ],
            "tools_used": self.tools_used,
            "submind_contributions": self.submind_contributions,
            "knowledge_blocks": self.knowledge_blocks,
            "confidence_score": self.confidence_score,
            "avg_trust_score": self.avg_trust_score,
            "model_used": self.model_used,
            "temperature": self.temperature,
            "created_at": self.created_at,
            "total_duration_ms": self.total_duration_ms
        }


class ResponseExplainer:
    """
    Central explainer for AI responses.
    
    Usage:
        explainer = ResponseExplainer()
        
        # Start explanation
        exp = explainer.create_explanation("resp_123", "User query", "AI response")
        
        # Add sources
        explainer.add_source(
            "resp_123",
            source_id="block_42",
            source_type="knowledge_block",
            content_snippet="...",
            trust_score=0.95
        )
        
        # Add reasoning steps
        explainer.add_reasoning_step(
            "resp_123",
            action="search_knowledge",
            description="Searched knowledge base"
        )
        
        # Save explanation
        explainer.save_explanation(exp)
    """
    
    def __init__(self):
        self.explanations: Dict[str, ResponseExplanation] = {}
        self.storage_dir = Path.home() / "ki_ana" / "explanations"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def create_explanation(
        self,
        response_id: str,
        query: str,
        response: str,
        model_used: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> ResponseExplanation:
        """Create a new explanation"""
        exp = ResponseExplanation(
            response_id=response_id,
            query=query,
            response=response,
            model_used=model_used,
            temperature=temperature
        )
        self.explanations[response_id] = exp
        return exp
    
    def add_source(
        self,
        response_id: str,
        source_id: str,
        source_type: str,
        content_snippet: str,
        trust_score: float = 0.0,
        url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add a source to an explanation"""
        if response_id not in self.explanations:
            return
        
        self.explanations[response_id].sources.append(
            ExplanationSource(
                source_id=source_id,
                source_type=source_type,
                content_snippet=content_snippet,
                trust_score=trust_score,
                timestamp=time.time(),
                url=url,
                metadata=metadata or {}
            )
        )
    
    def add_reasoning_step(
        self,
        response_id: str,
        action: str,
        description: str,
        result: Optional[str] = None,
        duration_ms: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add a reasoning step to an explanation"""
        if response_id not in self.explanations:
            return
        
        exp = self.explanations[response_id]
        step_number = len(exp.reasoning_steps) + 1
        
        exp.reasoning_steps.append(
            ExplanationStep(
                step_number=step_number,
                action=action,
                description=description,
                result=result,
                duration_ms=duration_ms,
                metadata=metadata or {}
            )
        )
    
    def add_tool_usage(
        self,
        response_id: str,
        tool_name: str,
        tool_input: Any,
        tool_output: Any,
        duration_ms: int = 0
    ):
        """Record tool usage"""
        if response_id not in self.explanations:
            return
        
        self.explanations[response_id].tools_used.append({
            "tool_name": tool_name,
            "input": str(tool_input)[:200],  # Truncate
            "output": str(tool_output)[:200],  # Truncate
            "duration_ms": duration_ms,
            "timestamp": time.time()
        })
    
    def add_submind_contribution(
        self,
        response_id: str,
        submind_id: str,
        contribution_type: str,
        contribution_data: Any
    ):
        """Record SubMind contribution"""
        if response_id not in self.explanations:
            return
        
        exp = self.explanations[response_id]
        if submind_id not in exp.submind_contributions:
            exp.submind_contributions[submind_id] = []
        
        exp.submind_contributions[submind_id].append({
            "type": contribution_type,
            "data": contribution_data,
            "timestamp": time.time()
        })
    
    def add_knowledge_block(
        self,
        response_id: str,
        block_index: int
    ):
        """Record knowledge block usage"""
        if response_id not in self.explanations:
            return
        
        exp = self.explanations[response_id]
        if block_index not in exp.knowledge_blocks:
            exp.knowledge_blocks.append(block_index)
    
    def finalize_explanation(
        self,
        response_id: str,
        total_duration_ms: int
    ):
        """Finalize explanation with computed metrics"""
        if response_id not in self.explanations:
            return
        
        exp = self.explanations[response_id]
        exp.total_duration_ms = total_duration_ms
        
        # Compute average trust score
        if exp.sources:
            exp.avg_trust_score = sum(s.trust_score for s in exp.sources) / len(exp.sources)
        
        # Compute confidence score (heuristic)
        confidence = 0.0
        
        # More sources = higher confidence (up to 0.3)
        source_factor = min(len(exp.sources) / 10.0, 0.3)
        
        # Higher trust = higher confidence (up to 0.4)
        trust_factor = exp.avg_trust_score * 0.4
        
        # More reasoning steps = higher confidence (up to 0.2)
        reasoning_factor = min(len(exp.reasoning_steps) / 5.0, 0.2)
        
        # Knowledge blocks used = higher confidence (up to 0.1)
        knowledge_factor = min(len(exp.knowledge_blocks) / 3.0, 0.1)
        
        confidence = source_factor + trust_factor + reasoning_factor + knowledge_factor
        exp.confidence_score = min(confidence, 1.0)
    
    def save_explanation(self, exp: ResponseExplanation):
        """Save explanation to disk"""
        try:
            exp_file = self.storage_dir / f"{exp.response_id}.json"
            exp_file.write_text(json.dumps(exp.to_dict(), indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"Failed to save explanation: {e}")
    
    def get_explanation(self, response_id: str) -> Optional[ResponseExplanation]:
        """Get explanation from memory or disk"""
        # Check memory first
        if response_id in self.explanations:
            return self.explanations[response_id]
        
        # Try to load from disk
        try:
            exp_file = self.storage_dir / f"{response_id}.json"
            if exp_file.exists():
                data = json.loads(exp_file.read_text())
                # Reconstruct (simplified - would need full reconstruction)
                return None  # TODO: Implement full reconstruction
        except Exception:
            pass
        
        return None
    
    def list_recent_explanations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent explanations"""
        explanations = []
        
        try:
            # Get all explanation files sorted by modification time
            files = sorted(
                self.storage_dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            for file in files[:limit]:
                try:
                    data = json.loads(file.read_text())
                    explanations.append({
                        "response_id": data.get("response_id"),
                        "query": data.get("query", "")[:100],
                        "confidence_score": data.get("confidence_score", 0.0),
                        "sources_count": len(data.get("sources", [])),
                        "created_at": data.get("created_at")
                    })
                except Exception:
                    continue
        
        except Exception:
            pass
        
        return explanations
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get explainer statistics"""
        total_files = len(list(self.storage_dir.glob("*.json")))
        
        # Compute from in-memory explanations
        in_memory = len(self.explanations)
        
        avg_sources = 0.0
        avg_steps = 0.0
        avg_confidence = 0.0
        
        if self.explanations:
            avg_sources = sum(len(e.sources) for e in self.explanations.values()) / len(self.explanations)
            avg_steps = sum(len(e.reasoning_steps) for e in self.explanations.values()) / len(self.explanations)
            avg_confidence = sum(e.confidence_score for e in self.explanations.values()) / len(self.explanations)
        
        return {
            "total_explanations": total_files,
            "in_memory": in_memory,
            "avg_sources_per_explanation": avg_sources,
            "avg_reasoning_steps": avg_steps,
            "avg_confidence_score": avg_confidence
        }


# Global instance
_explainer_instance: Optional[ResponseExplainer] = None


def get_explainer() -> ResponseExplainer:
    """Get or create global ResponseExplainer instance"""
    global _explainer_instance
    if _explainer_instance is None:
        _explainer_instance = ResponseExplainer()
    return _explainer_instance


# Context manager for easy explanation tracking
class ExplanationContext:
    """
    Context manager for tracking explanation.
    
    Usage:
        with ExplanationContext("query_123", "User question", "AI answer") as ctx:
            ctx.add_source("block_42", "knowledge_block", "...", trust_score=0.9)
            ctx.add_step("search", "Searched knowledge base")
            # ... more tracking
    """
    
    def __init__(self, response_id: str, query: str, response: str):
        self.response_id = response_id
        self.query = query
        self.response = response
        self.explainer = get_explainer()
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.explainer.create_explanation(self.response_id, self.query, self.response)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = int((time.time() - self.start_time) * 1000)
            self.explainer.finalize_explanation(self.response_id, duration_ms)
            
            exp = self.explainer.get_explanation(self.response_id)
            if exp:
                self.explainer.save_explanation(exp)
    
    def add_source(self, source_id: str, source_type: str, content_snippet: str, trust_score: float = 0.0, url: Optional[str] = None):
        """Add source"""
        self.explainer.add_source(self.response_id, source_id, source_type, content_snippet, trust_score, url)
    
    def add_step(self, action: str, description: str, result: Optional[str] = None):
        """Add reasoning step"""
        self.explainer.add_reasoning_step(self.response_id, action, description, result)
    
    def add_tool(self, tool_name: str, tool_input: Any, tool_output: Any):
        """Add tool usage"""
        self.explainer.add_tool_usage(self.response_id, tool_name, tool_input, tool_output)
    
    def add_submind(self, submind_id: str, contribution_type: str, data: Any):
        """Add SubMind contribution"""
        self.explainer.add_submind_contribution(self.response_id, submind_id, contribution_type, data)


if __name__ == "__main__":
    # Self-test
    print("=== Response Explainer Self-Test ===\n")
    
    # Test explanation creation
    explainer = ResponseExplainer()
    
    # Create explanation
    response_id = hashlib.md5(f"test_{time.time()}".encode()).hexdigest()[:12]
    exp = explainer.create_explanation(
        response_id=response_id,
        query="What is Python?",
        response="Python is a high-level programming language.",
        model_used="llama3.2",
        temperature=0.7
    )
    
    # Add sources
    explainer.add_source(
        response_id,
        source_id="block_42",
        source_type="knowledge_block",
        content_snippet="Python is a programming language...",
        trust_score=0.95,
        url="internal://block/42"
    )
    
    explainer.add_source(
        response_id,
        source_id="web_1",
        source_type="web",
        content_snippet="Python.org official documentation",
        trust_score=1.0,
        url="https://python.org"
    )
    
    # Add reasoning steps
    explainer.add_reasoning_step(
        response_id,
        action="search_knowledge",
        description="Searched knowledge base for 'Python'",
        result="Found 2 relevant blocks",
        duration_ms=50
    )
    
    explainer.add_reasoning_step(
        response_id,
        action="synthesize",
        description="Synthesized answer from sources",
        result="Generated response",
        duration_ms=120
    )
    
    # Add tool usage
    explainer.add_tool_usage(
        response_id,
        tool_name="vector_search",
        tool_input="Python programming",
        tool_output="[block_42, block_78]",
        duration_ms=35
    )
    
    # Add SubMind contribution
    explainer.add_submind_contribution(
        response_id,
        submind_id="researcher_1",
        contribution_type="fact_check",
        contribution_data={"verified": True, "sources": 2}
    )
    
    # Add knowledge blocks
    explainer.add_knowledge_block(response_id, 42)
    explainer.add_knowledge_block(response_id, 78)
    
    # Finalize
    explainer.finalize_explanation(response_id, total_duration_ms=250)
    
    # Save
    explainer.save_explanation(exp)
    
    # Display results
    print(f"Response ID: {response_id}")
    print(f"Sources: {len(exp.sources)}")
    print(f"Reasoning Steps: {len(exp.reasoning_steps)}")
    print(f"Tools Used: {len(exp.tools_used)}")
    print(f"SubMind Contributions: {len(exp.submind_contributions)}")
    print(f"Knowledge Blocks: {len(exp.knowledge_blocks)}")
    print(f"Confidence Score: {exp.confidence_score:.2f}")
    print(f"Average Trust Score: {exp.avg_trust_score:.2f}")
    print(f"Total Duration: {exp.total_duration_ms}ms")
    
    # Statistics
    stats = explainer.get_statistics()
    print(f"\nStatistics:")
    print(f"  Total Explanations: {stats['total_explanations']}")
    print(f"  Avg Sources: {stats['avg_sources_per_explanation']:.1f}")
    print(f"  Avg Steps: {stats['avg_reasoning_steps']:.1f}")
    
    print("\n✅ Response Explainer functional!")
