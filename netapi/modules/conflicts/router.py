"""
Conflict Resolution API Router

Provides endpoints for detecting and resolving knowledge conflicts.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import Dict, Any, List
import sys

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

router = APIRouter(prefix="/api/conflicts", tags=["conflicts"])


@router.get("/stats")
async def get_conflict_stats():
    """Get conflict resolution statistics."""
    try:
        from conflict_resolver import get_conflict_resolver
        resolver = get_conflict_resolver()
        stats = resolver.get_stats()
        return {"ok": True, "stats": stats}
    except Exception as e:
        raise HTTPException(500, f"failed to get stats: {e}")


@router.post("/scan/{topic}")
async def scan_topic_for_conflicts(topic: str):
    """Scan a specific topic for conflicts."""
    try:
        from conflict_resolver import get_conflict_resolver
        
        # Load blocks for topic
        from netapi import memory_store as mem
        
        # Search for blocks on this topic
        results = mem.search_blocks(topic, top_k=50, min_score=0.1)
        
        if not results:
            return {"ok": True, "conflicts": [], "message": "No blocks found for topic"}
        
        # Get full blocks
        blocks = []
        for block_id, score in results:
            block = mem.get_block(block_id)
            if block:
                blocks.append(block)
        
        # Detect conflicts
        resolver = get_conflict_resolver()
        conflicts = resolver.detect_conflicts_by_topic(topic, blocks)
        
        return {
            "ok": True,
            "topic": topic,
            "blocks_checked": len(blocks),
            "conflicts_found": len(conflicts),
            "conflicts": [c.to_dict() for c in conflicts]
        }
    except Exception as e:
        raise HTTPException(500, f"failed to scan: {e}")


@router.post("/resolve/{block_a_id}/{block_b_id}")
async def resolve_conflict_between_blocks(block_a_id: str, block_b_id: str):
    """Manually trigger resolution between two blocks."""
    try:
        from conflict_resolver import get_conflict_resolver, Conflict
        from netapi import memory_store as mem
        
        # Load blocks
        block_a = mem.get_block(block_a_id)
        block_b = mem.get_block(block_b_id)
        
        if not block_a or not block_b:
            raise HTTPException(404, "one or both blocks not found")
        
        # Create a conflict object
        conflict = Conflict(
            block_a_id=block_a_id,
            block_b_id=block_b_id,
            conflict_type="manual",
            topic=block_a.get("topic", "unknown"),
            detected_at=time.time(),
            confidence=1.0
        )
        
        # Resolve
        resolver = get_conflict_resolver()
        resolution = resolver.resolve_conflict(conflict, block_a, block_b)
        
        # Apply resolution
        result = resolver.apply_resolution(resolution)
        
        return {
            "ok": True,
            "resolution": resolution.to_dict(),
            "action": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"failed to resolve: {e}")


@router.post("/scan/all")
async def scan_all_topics():
    """Scan all topics for conflicts (can be slow!)."""
    try:
        from conflict_resolver import get_conflict_resolver
        from netapi import memory_store as mem
        
        # Get all unique topics
        # This is a simplified version - in production, you'd want pagination
        all_blocks = []
        
        # Search for common topics
        common_topics = [
            "python", "ki", "photosynthese", "erde", "geschichte",
            "technologie", "wissenschaft", "mathematik"
        ]
        
        topics_checked = 0
        total_conflicts = []
        
        for topic in common_topics:
            results = mem.search_blocks(topic, top_k=20, min_score=0.2)
            if results:
                blocks = [mem.get_block(bid) for bid, _ in results if mem.get_block(bid)]
                
                resolver = get_conflict_resolver()
                conflicts = resolver.detect_conflicts_by_topic(topic, blocks)
                
                if conflicts:
                    total_conflicts.extend(conflicts)
                    topics_checked += 1
        
        return {
            "ok": True,
            "topics_checked": topics_checked,
            "conflicts_found": len(total_conflicts),
            "conflicts": [c.to_dict() for c in total_conflicts[:20]]  # Limit response size
        }
    except Exception as e:
        raise HTTPException(500, f"failed to scan all: {e}")


import time
