"""
Redis Cache for RAG System (fixed for older Redis versions)
"""

import json
import hashlib
from typing import Any, Optional
import redis
from backend.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, CACHE_TTL_SECONDS, CACHE_ENABLED

class RedisCache:
    def __init__(self):
        if CACHE_ENABLED:
            try:
                self.client = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    password=REDIS_PASSWORD,
                    decode_responses=True,
                    protocol=2  # <-- CRITICAL FIX: force RESP2 for older Redis
                )
                # Test connection
                self.client.ping()
                print("✅ Redis connected successfully (RESP2)")
            except Exception as e:
                print(f"⚠️ Redis connection failed: {e}")
                self.client = None
        else:
            self.client = None
            print("ℹ️ Redis cache is disabled")

    def _get_key(self, query: str) -> str:
        """Generate a consistent cache key from the query string."""
        return f"rag:query:{hashlib.sha256(query.encode()).hexdigest()}"

    def get(self, query: str) -> Optional[Any]:
        """Retrieve cached result for a query."""
        if not self.client or not CACHE_ENABLED:
            return None
        key = self._get_key(query)
        raw = self.client.get(key)
        if raw:
            try:
                return json.loads(raw)
            except:
                return None
        return None

    def set(self, query: str, value: Any, ttl: int = None) -> bool:
        """Store result in cache with TTL (default from config)."""
        if not self.client or not CACHE_ENABLED:
            return False
        key = self._get_key(query)
        try:
            serialized = json.dumps(value, default=str)
        except Exception as e:
            print(f"❌ Serialization error for cache: {e}")
            return False
        ttl = ttl or CACHE_TTL_SECONDS
        return self.client.setex(key, ttl, serialized)

    def clear(self, pattern: str = "rag:query:*") -> int:
        """Clear cache entries matching a pattern (for admin use)."""
        if not self.client:
            return 0
        keys = self.client.keys(pattern)
        if keys:
            return self.client.delete(*keys)
        return 0

# Singleton instance
cache = RedisCache()