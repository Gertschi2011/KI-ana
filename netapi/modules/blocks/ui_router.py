"""
Block Viewer & Settings Panel Router

Provides UI-friendly endpoints for block management and settings.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ...deps import get_db, get_current_user_required
from ...models import User
from loguru import logger


router = APIRouter(prefix="/api/blocks/ui", tags=["blocks-ui"])


class BlockFilter(BaseModel):
    """Filter parameters for block viewer"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    source_filter: Optional[List[str]] = None
    min_rating: Optional[float] = None
    max_rating: Optional[float] = None
    language: Optional[str] = None
    sub_ki_filter: Optional[List[str]] = None


class SettingsUpdate(BaseModel):
    """User settings for blocks"""
    enable_ethics_filter: bool = True
    preferred_languages: List[str] = ["de", "en"]
    trusted_sources: List[str] = []
    blocked_sources: List[str] = []
    min_trust_score: float = 50.0
    enable_sub_kis: List[str] = []


@router.get("/blocks")
async def get_blocks_filtered(
    page: int = 1,
    per_page: int = 20,
    source: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_rating: Optional[float] = None,
    language: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Get blocks with filtering and pagination
    
    Returns blocks with:
    - Source information
    - Trust ratings
    - Timestamps
    - Content preview
    - Related Sub-KI
    """
    try:
        # This is a simplified version - integrate with actual blockchain
        # For now, return mock data structure
        
        blocks = []
        
        # Apply filters
        # (In production, query actual blockchain)
        
        # Mock data for demonstration
        for i in range(1, min(per_page + 1, 21)):
            block = {
                "id": f"block_{page}_{i}",
                "timestamp": datetime.now().isoformat(),
                "source": {
                    "url": f"https://example.com/article{i}",
                    "domain": "example.com",
                    "title": f"Article {i}"
                },
                "trust_rating": {
                    "overall_score": 75.5 + i,
                    "trust_score": 80.0,
                    "quality_score": 70.0,
                    "rating": "Good"
                },
                "content_preview": f"This is a preview of block {i}...",
                "language": "de",
                "sub_ki_id": "kiana-os-local",
                "metadata": {
                    "crawled_at": datetime.now().isoformat(),
                    "word_count": 500 + i * 10
                }
            }
            blocks.append(block)
        
        return {
            "success": True,
            "blocks": blocks,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": 100,  # Mock total
                "total_pages": 5
            },
            "filters_applied": {
                "source": source,
                "start_date": start_date,
                "end_date": end_date,
                "min_rating": min_rating,
                "language": language
            }
        }
        
    except Exception as e:
        logger.error(f"Block retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_block_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Get block statistics for dashboard
    
    Returns:
    - Total blocks
    - Blocks by source
    - Average trust score
    - Language distribution
    - Sub-KI contribution
    """
    try:
        # Mock stats
        stats = {
            "total_blocks": 1234,
            "blocks_today": 45,
            "blocks_this_week": 312,
            "average_trust_score": 76.8,
            "by_source": {
                "wikipedia.org": 234,
                "arxiv.org": 123,
                "github.com": 89,
                "other": 788
            },
            "by_language": {
                "de": 789,
                "en": 445
            },
            "by_sub_ki": {
                "kiana-os-local": 567,
                "kiana-os-remote-1": 234,
                "kiana-os-remote-2": 433
            },
            "trust_distribution": {
                "excellent": 234,
                "very_good": 345,
                "good": 456,
                "fair": 123,
                "moderate": 76
            }
        }
        
        return {
            "success": True,
            "stats": stats,
            "updated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Stats retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings")
async def get_user_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Get user's block settings
    """
    try:
        # Get from database (simplified)
        settings = {
            "enable_ethics_filter": True,
            "preferred_languages": ["de", "en"],
            "trusted_sources": [
                "wikipedia.org",
                "arxiv.org",
                "github.com"
            ],
            "blocked_sources": [
                "spam-site.com"
            ],
            "min_trust_score": 60.0,
            "enable_sub_kis": [
                "kiana-os-local",
                "kiana-os-remote-1"
            ],
            "auto_sync": True,
            "notifications": {
                "new_blocks": True,
                "low_trust_warning": True,
                "sub_ki_updates": False
            }
        }
        
        return {
            "success": True,
            "settings": settings
        }
        
    except Exception as e:
        logger.error(f"Settings retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings")
async def update_user_settings(
    settings: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Update user's block settings
    """
    try:
        # Save to database (simplified)
        logger.info(f"Updating settings for user {current_user.id}")
        
        # In production: store in database
        # user.settings = settings.dict()
        # db.commit()
        
        return {
            "success": True,
            "message": "Settings updated",
            "settings": settings.dict()
        }
        
    except Exception as e:
        logger.error(f"Settings update failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources")
async def get_available_sources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Get list of available sources with ratings
    """
    try:
        # Get from trust rating system
        from netapi.modules.crawler.trust_rating import get_trust_rating
        trust_rating = get_trust_rating()
        
        sources = []
        for domain, base_score in trust_rating.trusted_domains.items():
            sources.append({
                "domain": domain,
                "base_score": base_score * 100,
                "category": "trusted"
            })
        
        return {
            "success": True,
            "sources": sources,
            "total": len(sources)
        }
        
    except Exception as e:
        logger.error(f"Source retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sub-kis")
async def get_available_sub_kis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Get list of available Sub-KIs
    """
    try:
        sub_kis = [
            {
                "id": "kiana-os-local",
                "name": "KI-ana OS (Local)",
                "status": "active",
                "last_seen": datetime.now().isoformat(),
                "blocks_contributed": 567
            },
            {
                "id": "kiana-os-remote-1",
                "name": "KI-ana OS (Remote 1)",
                "status": "active",
                "last_seen": (datetime.now() - timedelta(minutes=5)).isoformat(),
                "blocks_contributed": 234
            },
            {
                "id": "kiana-os-remote-2",
                "name": "KI-ana OS (Remote 2)",
                "status": "inactive",
                "last_seen": (datetime.now() - timedelta(hours=2)).isoformat(),
                "blocks_contributed": 433
            }
        ]
        
        return {
            "success": True,
            "sub_kis": sub_kis,
            "total": len(sub_kis),
            "active_count": sum(1 for sk in sub_kis if sk["status"] == "active")
        }
        
    except Exception as e:
        logger.error(f"Sub-KI retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
