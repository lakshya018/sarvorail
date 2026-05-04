"""
In-memory TTL cache using cachetools for Render free-tier compatibility.
"""
import logging
from cachetools import TTLCache
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)

# Cache configuration
# - 1000 max entries (prevents unbounded memory growth)
# - 300 seconds (5 minutes) for availability data
# - 86400 seconds (24 hours) for route results
cache = TTLCache(maxsize=1000, ttl=300)

# Separate long-lived cache for routes (24h)
routes_cache: Dict[str, Any] = {}
routes_ttl = 86400

# Track when routes entries were added for manual expiry
routes_timestamps = {}


def get(key: str) -> Optional[Any]:
    """Get value from cache if it exists."""
    try:
        return cache.get(key)
    except KeyError:
        return None


def set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    """
    Set value in cache with TTL.
    For long-lived caches (ttl > 3600), use routes_cache instead.
    """
    try:
        if ttl_seconds > 3600:
            # Use manual long-lived cache for routes
            routes_cache[key] = value
            routes_timestamps[key] = __import__('time').time()
            logger.debug(f"Cached (long-lived): {key}")
        else:
            # Use TTLCache for shorter-lived data
            cache[key] = value
            logger.debug(f"Cached: {key}")
    except Exception as e:
        logger.error(f"Cache set error for {key}: {e}")


def exists(key: str) -> bool:
    """Check if key exists in cache."""
    if key in cache:
        return True
    if key in routes_cache:
        # Check if expired manually
        import time
        if time.time() - routes_timestamps.get(key, 0) < routes_ttl:
            return True
        else:
            # Expired, clean up
            routes_cache.pop(key, None)
            routes_timestamps.pop(key, None)
            return False
    return False


def delete(key: str) -> None:
    """Delete key from cache."""
    try:
        cache.pop(key, None)
        routes_cache.pop(key, None)
        routes_timestamps.pop(key, None)
    except Exception as e:
        logger.error(f"Cache delete error for {key}: {e}")


def clear() -> None:
    """Clear all cached data."""
    cache.clear()
    routes_cache.clear()
    routes_timestamps.clear()
    logger.info("Cache cleared")


# TTL constants (for backward compatibility)
TRAINS_BETWEEN_TTL = 86400        # 24h
TRAINS_BETWEEN_PERM_TTL = 2592000  # 30 days (not used with in-memory)
TRAIN_SCHEDULE_PERM_TTL = 2592000  # 30 days (not used with in-memory)
AVAILABILITY_TTL = 300             # 5 minutes
