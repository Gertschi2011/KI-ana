"""
Addressbook API Router
Provides endpoints for topic tree navigation and search
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
from .indexer import AddressbookIndexer, build_addressbook_index


router = APIRouter(prefix="/api/addressbook", tags=["addressbook"])

INDEX_FILE = Path("/home/kiana/ki_ana/data/addressbook.index.json")


def _load_index() -> Dict[str, Any]:
    """Load index from file"""
    if not INDEX_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="Index not found. Please run indexer first."
        )
    
    try:
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load index: {str(e)}"
        )


def _find_node_by_path(tree: Dict[str, Any], path: List[str]) -> Optional[Dict[str, Any]]:
    """Find a node in the tree by path"""
    if not path:
        return tree
    
    current = tree
    for part in path:
        found = False
        for child in current.get("children", []):
            if child["name"] == part:
                current = child
                found = True
                break
        
        if not found:
            return None
    
    return current


def _search_tree(tree: Dict[str, Any], query: str, results: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Recursively search tree for matching nodes"""
    if results is None:
        results = []
    
    query_lower = query.lower()
    
    # Check if current node matches
    if query_lower in tree["name"].lower():
        results.append({
            "name": tree["name"],
            "path": tree["path"],
            "count": tree["count"],
            "blocks_count": tree.get("blocks_count", 0)
        })
    
    # Search children
    for child in tree.get("children", []):
        _search_tree(child, query, results)
    
    return results


@router.get("/tree")
async def get_tree(
    max_depth: Optional[int] = Query(None, description="Maximum depth to return"),
    include_blocks: bool = Query(False, description="Include block listings")
):
    """
    Get complete topic tree
    
    Returns hierarchical structure of all topics with counts.
    """
    index = _load_index()
    tree_obj = index.get("tree", {})
    stats = index.get("stats", {})
    
    # Frontend expects tree object with children, not a list!
    # Keep the original tree structure
    
    # TODO: Implement depth limiting if max_depth is set
    # TODO: Strip blocks if include_blocks is False
    
    return {
        "ok": True,
        "tree": tree_obj,  # Return the full tree object, not just children
        "stats": stats
    }


@router.get("/list")
async def list_blocks(
    path: str = Query(..., description="Topic path (e.g. 'Geschichte/Hitler')"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=200, description="Items per page"),
    sort_by: str = Query("timestamp", description="Sort field: timestamp, trust, title"),
    order: str = Query("desc", description="Sort order: asc, desc")
):
    """
    List blocks for a specific topic path
    
    Returns paginated list of blocks with metadata.
    """
    index = _load_index()
    tree = index.get("tree", {})
    
    # Parse path
    path_parts = [p.strip() for p in path.split('/') if p.strip()]
    
    # Find node
    node = _find_node_by_path(tree, path_parts)
    
    if not node:
        raise HTTPException(
            status_code=404,
            detail=f"Path not found: {path}"
        )
    
    # Load actual blocks from files
    import os
    KI_ROOT = Path(os.getenv("KI_ROOT", "/home/kiana/ki_ana"))
    candidate_dirs = [
        KI_ROOT / "memory" / "long_term" / "blocks",
        KI_ROOT / "data" / "blocks",
    ]
    
    blocks: List[Dict[str, Any]] = []
    for blocks_dir in candidate_dirs:
        if not blocks_dir.exists():
            continue
        for block_file in blocks_dir.rglob("*.json"):
            try:
                with open(block_file, 'r', encoding='utf-8') as f:
                    block_data = json.load(f)
                
                # Check if block matches path
                block_topics_path = (
                    block_data.get("topics_path")
                    or block_data.get("topic_path")
                    or block_data.get("topics")
                    or block_data.get("tags")
                    or []
                )
                if isinstance(block_topics_path, str):
                    block_topics_path = [p.strip() for p in block_topics_path.split('/') if p.strip()]
                if not isinstance(block_topics_path, list):
                    continue
                
                # Match path: check if block's path starts with requested path
                if len(block_topics_path) >= len(path_parts):
                    matches = all(
                        block_topics_path[i].lower() == path_parts[i].lower()
                        for i in range(len(path_parts))
                    )
                    
                    if matches:
                        blocks.append({
                            "id": block_data.get("id") or block_file.stem,
                            "title": block_data.get("title", "Untitled"),
                            "timestamp": block_data.get("timestamp", block_data.get("created_at", block_data.get("created", 0))),
                            "trust": block_data.get("trust", block_data.get("trust_score", 5)),
                            "source": block_data.get("source", ""),
                            "topics_path": block_topics_path
                        })
            except Exception:
                continue
    
    # Sort blocks
    if sort_by == "timestamp":
        blocks.sort(key=lambda x: x.get("timestamp", 0), reverse=(order == "desc"))
    elif sort_by == "trust":
        blocks.sort(key=lambda x: x.get("trust", 0), reverse=(order == "desc"))
    elif sort_by == "title":
        blocks.sort(key=lambda x: x.get("title", "").lower(), reverse=(order == "desc"))
    
    # Pagination
    total = len(blocks)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_blocks = blocks[start:end]
    
    return {
        "ok": True,
        "path": path_parts,
        "node": {
            "name": node["name"],
            "path": node["path"],
            "count": node["count"],
            "blocks_count": len(blocks)
        },
        "blocks": paginated_blocks,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page
        }
    }


@router.get("/search")
async def search_topics(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results")
):
    """
    Fuzzy search in topic tree
    
    Searches topic names and returns matching paths.
    """
    index = _load_index()
    tree = index.get("tree", {})
    
    # Search tree
    results = _search_tree(tree, q)
    
    # Limit results
    results = results[:limit]
    
    # Sort by relevance (exact matches first, then by count)
    results.sort(
        key=lambda x: (
            0 if x["name"].lower() == q.lower() else 1,
            -x["count"]
        )
    )
    
    return {
        "ok": True,
        "query": q,
        "results": results,
        "count": len(results)
    }


@router.post("/rebuild")
async def rebuild_index(
    blocks_dir: Optional[str] = None
):
    """
    Rebuild index from scratch
    
    Scans all blocks and regenerates the topic tree.
    (Requires admin permissions in production)
    """
    try:
        result = build_addressbook_index(blocks_dir)
        return {
            "ok": True,
            "message": "Index rebuilt successfully",
            "stats": result.get("stats", {})
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to rebuild index: {str(e)}"
        )


@router.get("/stats")
async def get_stats():
    """
    Get index statistics
    
    Returns metadata about the index.
    """
    index = _load_index()
    stats = index.get("stats", {})
    
    return {
        "ok": True,
        "stats": stats,
        "version": index.get("version", "unknown")
    }
