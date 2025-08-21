"""
Redis caching layer for frequently accessed data.
Optimizes database queries and improves response times.
"""
import redis
import json
import os
from typing import Optional, Dict, Any, List
from .logger import logger

# Redis configuration
REDIS_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")

# Cache TTL settings (in seconds)
CACHE_TTL_EDIT_STATUS = 30  # Status checks are frequent, short TTL
CACHE_TTL_EDIT_FEEDBACK = 300  # Feedback rarely changes
CACHE_TTL_CHAIN_HISTORY = 60  # Chain history changes when new edits are added

# Global Redis client
_redis_client = None

def get_redis_client():
    """Get or create Redis client with connection pooling"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            max_connections=10,  # Connection pooling
            socket_keepalive=True,
            socket_keepalive_options={},
            health_check_interval=30
        )
    return _redis_client

def _make_key(prefix: str, identifier: str) -> str:
    """Create cache key with environment prefix"""
    return f"{ENVIRONMENT}:cache:{prefix}:{identifier}"

def cache_edit_status(edit_uuid: str, status_data: Dict[str, Any]) -> None:
    """Cache edit status data"""
    try:
        client = get_redis_client()
        key = _make_key("edit_status", edit_uuid)
        client.setex(key, CACHE_TTL_EDIT_STATUS, json.dumps(status_data))
        logger.debug(f"Cached edit status for {edit_uuid}")
    except Exception as e:
        logger.warning(f"Failed to cache edit status: {e}")

def get_cached_edit_status(edit_uuid: str) -> Optional[Dict[str, Any]]:
    """Get cached edit status data"""
    try:
        client = get_redis_client()
        key = _make_key("edit_status", edit_uuid)
        cached_data = client.get(key)
        if cached_data:
            logger.debug(f"Cache hit for edit status {edit_uuid}")
            return json.loads(cached_data)
        return None
    except Exception as e:
        logger.warning(f"Failed to get cached edit status: {e}")
        return None

def invalidate_edit_status(edit_uuid: str) -> None:
    """Invalidate cached edit status when it changes"""
    try:
        client = get_redis_client()
        key = _make_key("edit_status", edit_uuid)
        client.delete(key)
        logger.debug(f"Invalidated edit status cache for {edit_uuid}")
    except Exception as e:
        logger.warning(f"Failed to invalidate edit status cache: {e}")

def cache_edit_feedback(edit_uuid: str, feedback_data: Dict[str, Any]) -> None:
    """Cache edit feedback data (feedback rarely changes)"""
    try:
        client = get_redis_client()
        key = _make_key("edit_feedback", edit_uuid)
        client.setex(key, CACHE_TTL_EDIT_FEEDBACK, json.dumps(feedback_data))
        logger.debug(f"Cached edit feedback for {edit_uuid}")
    except Exception as e:
        logger.warning(f"Failed to cache edit feedback: {e}")

def get_cached_edit_feedback(edit_uuid: str) -> Optional[Dict[str, Any]]:
    """Get cached edit feedback data"""
    try:
        client = get_redis_client()
        key = _make_key("edit_feedback", edit_uuid)
        cached_data = client.get(key)
        if cached_data:
            logger.debug(f"Cache hit for edit feedback {edit_uuid}")
            return json.loads(cached_data)
        return None
    except Exception as e:
        logger.warning(f"Failed to get cached edit feedback: {e}")
        return None

def cache_chain_history(edit_uuid: str, chain_data: List[Dict[str, Any]]) -> None:
    """Cache edit chain history"""
    try:
        client = get_redis_client()
        key = _make_key("chain_history", edit_uuid)
        client.setex(key, CACHE_TTL_CHAIN_HISTORY, json.dumps(chain_data))
        logger.debug(f"Cached chain history for {edit_uuid}")
    except Exception as e:
        logger.warning(f"Failed to cache chain history: {e}")

def get_cached_chain_history(edit_uuid: str) -> Optional[List[Dict[str, Any]]]:
    """Get cached edit chain history"""
    try:
        client = get_redis_client()
        key = _make_key("chain_history", edit_uuid)
        cached_data = client.get(key)
        if cached_data:
            logger.debug(f"Cache hit for chain history {edit_uuid}")
            return json.loads(cached_data)
        return None
    except Exception as e:
        logger.warning(f"Failed to get cached chain history: {e}")
        return None

def invalidate_chain_history(edit_uuid: str) -> None:
    """Invalidate cached chain history when new edit is added"""
    try:
        client = get_redis_client()
        key = _make_key("chain_history", edit_uuid)
        client.delete(key)
        logger.debug(f"Invalidated chain history cache for {edit_uuid}")
    except Exception as e:
        logger.warning(f"Failed to invalidate chain history cache: {e}")

def clear_all_cache() -> None:
    """Clear all cache entries (useful for debugging)"""
    try:
        client = get_redis_client()
        pattern = f"{ENVIRONMENT}:cache:*"
        keys = client.keys(pattern)
        if keys:
            client.delete(*keys)
            logger.info(f"Cleared {len(keys)} cache entries")
    except Exception as e:
        logger.warning(f"Failed to clear cache: {e}")

def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    try:
        client = get_redis_client()
        info = client.info()
        pattern = f"{ENVIRONMENT}:cache:*"
        keys = client.keys(pattern)
        
        return {
            "total_keys": len(keys),
            "memory_used": info.get("used_memory_human", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "environment": ENVIRONMENT
        }
    except Exception as e:
        logger.warning(f"Failed to get cache stats: {e}")
        return {"error": str(e)}