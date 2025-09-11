"""Cleanup tasks for maintenance operations (PRP 18)."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.models.database import get_db_session
from src.models.entities import QueryResponseCache
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def cleanup_expired_viewer_cache(db: Optional[Session] = None) -> int:
    """Remove expired viewer cache entries."""
    if not db:
        db = next(get_db_session())
    
    try:
        # Get current time
        now = datetime.utcnow()
        
        # Find expired entries
        expired_query = select(QueryResponseCache).where(
            QueryResponseCache.expires_at < now
        )
        expired_entries = db.execute(expired_query).scalars().all()
        
        if not expired_entries:
            logger.info("No expired viewer cache entries found")
            return 0
        
        # Delete expired entries
        delete_count = len(expired_entries)
        
        for entry in expired_entries:
            db.delete(entry)
        
        db.commit()
        
        logger.info(
            f"Cleaned up {delete_count} expired viewer cache entries",
            extra_fields={"deleted_count": delete_count}
        )
        
        return delete_count
        
    except Exception as e:
        logger.error(f"Failed to cleanup expired viewer cache: {e}")
        db.rollback()
        raise
    finally:
        db.close()


async def cleanup_old_viewer_cache_by_age(
    max_age_hours: int = 24,
    db: Optional[Session] = None
) -> int:
    """Remove viewer cache entries older than specified age."""
    if not db:
        db = next(get_db_session())
    
    try:
        # Calculate cutoff time
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        # Find old entries
        old_query = select(QueryResponseCache).where(
            QueryResponseCache.created_at < cutoff_time
        )
        old_entries = db.execute(old_query).scalars().all()
        
        if not old_entries:
            logger.info(f"No viewer cache entries older than {max_age_hours} hours found")
            return 0
        
        # Delete old entries
        delete_count = len(old_entries)
        
        for entry in old_entries:
            db.delete(entry)
        
        db.commit()
        
        logger.info(
            f"Cleaned up {delete_count} old viewer cache entries",
            extra_fields={
                "deleted_count": delete_count,
                "max_age_hours": max_age_hours
            }
        )
        
        return delete_count
        
    except Exception as e:
        logger.error(f"Failed to cleanup old viewer cache: {e}")
        db.rollback()
        raise
    finally:
        db.close()


async def get_viewer_cache_stats(db: Optional[Session] = None) -> dict:
    """Get statistics about viewer cache."""
    if not db:
        db = next(get_db_session())
    
    try:
        now = datetime.utcnow()
        
        # Total entries
        total_query = select(QueryResponseCache)
        total_count = len(db.execute(total_query).scalars().all())
        
        # Expired entries
        expired_query = select(QueryResponseCache).where(
            QueryResponseCache.expires_at < now
        )
        expired_count = len(db.execute(expired_query).scalars().all())
        
        # Entries from last 24 hours
        recent_cutoff = now - timedelta(hours=24)
        recent_query = select(QueryResponseCache).where(
            QueryResponseCache.created_at >= recent_cutoff
        )
        recent_count = len(db.execute(recent_query).scalars().all())
        
        stats = {
            "total_entries": total_count,
            "expired_entries": expired_count,
            "active_entries": total_count - expired_count,
            "recent_entries_24h": recent_count,
            "timestamp": now.isoformat()
        }
        
        logger.info("Viewer cache statistics collected", extra_fields=stats)
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get viewer cache stats: {e}")
        raise
    finally:
        db.close()


async def scheduled_cleanup_task():
    """Scheduled cleanup task to run periodically."""
    get_settings()
    
    logger.info("Starting scheduled viewer cache cleanup")
    
    try:
        # Get stats before cleanup
        stats_before = await get_viewer_cache_stats()
        
        # Cleanup expired entries
        expired_cleaned = await cleanup_expired_viewer_cache()
        
        # Also cleanup very old entries (older than 7 days)
        old_cleaned = await cleanup_old_viewer_cache_by_age(max_age_hours=168)  # 7 days
        
        # Get stats after cleanup
        stats_after = await get_viewer_cache_stats()
        
        logger.info(
            "Scheduled cleanup completed",
            extra_fields={
                "expired_cleaned": expired_cleaned,
                "old_cleaned": old_cleaned,
                "total_cleaned": expired_cleaned + old_cleaned,
                "entries_before": stats_before["total_entries"],
                "entries_after": stats_after["total_entries"]
            }
        )
        
        return {
            "expired_cleaned": expired_cleaned,
            "old_cleaned": old_cleaned,
            "total_cleaned": expired_cleaned + old_cleaned,
            "stats_before": stats_before,
            "stats_after": stats_after
        }
        
    except Exception as e:
        logger.error(f"Scheduled cleanup task failed: {e}")
        raise


def run_cleanup_sync():
    """Synchronous wrapper for cleanup task (for CLI usage)."""
    return asyncio.run(scheduled_cleanup_task())


if __name__ == "__main__":
    # Allow running cleanup directly
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        stats = asyncio.run(get_viewer_cache_stats())
        print("Viewer Cache Statistics:")
        print(f"  Total entries: {stats['total_entries']}")
        print(f"  Active entries: {stats['active_entries']}")
        print(f"  Expired entries: {stats['expired_entries']}")
        print(f"  Recent entries (24h): {stats['recent_entries_24h']}")
    else:
        result = run_cleanup_sync()
        print(f"Cleanup completed. Removed {result['total_cleaned']} entries.")