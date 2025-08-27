"""
Cache Manager - Centralized Caching System

Provides centralized caching for embeddings, LLM responses, retrievers, and other expensive operations.
Features TTL-based expiration, size limits, and performance monitoring.
"""

import asyncio
import hashlib
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Callable
from functools import lru_cache
import logging

from app.settings import settings

logger = logging.getLogger(__name__)


class CacheEntry:
    """Represents a cached entry with metadata."""

    def __init__(self, value: Any, ttl_seconds: float, created_at: Optional[float] = None):
        self.value = value
        self.ttl_seconds = ttl_seconds
        self.created_at = created_at or time.monotonic()
        self.access_count = 0
        self.last_accessed = self.created_at

    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        return (time.monotonic() - self.created_at) > self.ttl_seconds

    def access(self) -> Any:
        """Access the entry and update metadata."""
        self.access_count += 1
        self.last_accessed = time.monotonic()
        return self.value

    def get_age_seconds(self) -> float:
        """Get the age of this entry in seconds."""
        return time.monotonic() - self.created_at


class CacheManager:
    """
    Centralized cache manager for all agent operations.

    Features:
    - TTL-based expiration
    - Size limits with LRU eviction
    - Performance monitoring
    - Thread-safe operations
    - Async support
    """

    _instance: Optional["CacheManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "CacheManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._lock = threading.RLock()

        # Cache stores
        self._embedding_cache: Dict[str, CacheEntry] = {}
        self._llm_cache: Dict[str, CacheEntry] = {}
        self._retriever_cache: Dict[str, CacheEntry] = {}
        self._general_cache: Dict[str, CacheEntry] = {}

        # Configuration
        self._embedding_cache_size = getattr(settings, "embedding_cache_size", 1000)
        self._llm_cache_size = getattr(settings, "llm_cache_size", 500)
        self._retriever_cache_size = getattr(settings, "retriever_cache_size", 10)
        self._general_cache_size = getattr(settings, "general_cache_size", 100)

        # TTL settings
        self._embedding_ttl = getattr(settings, "embedding_cache_ttl", 3600)  # 1 hour
        self._llm_ttl = getattr(settings, "llm_cache_ttl", 300)  # 5 minutes
        self._retriever_ttl = getattr(settings, "retriever_cache_ttl", 600)  # 10 minutes
        self._general_ttl = getattr(settings, "general_cache_ttl", 300)  # 5 minutes

        # Performance tracking
        self._hits = 0
        self._misses = 0
        self._evictions = 0

        logger.info(
            f"CacheManager initialized with sizes: emb={self._embedding_cache_size}, "
            f"llm={self._llm_cache_size}, ret={self._retriever_cache_size}, gen={self._general_cache_size}"
        )

    def _get_cache_key(self, key: str, namespace: str = "") -> str:
        """Generate a cache key with optional namespace."""
        if namespace:
            return f"{namespace}:{key}"
        return key

    def _cleanup_expired(self, cache: Dict[str, CacheEntry]) -> int:
        """Remove expired entries from a cache. Returns number of entries removed."""
        expired_keys = []
        for key, entry in cache.items():
            if entry.is_expired():
                expired_keys.append(key)

        for key in expired_keys:
            del cache[key]

        return len(expired_keys)

    def _evict_lru(self, cache: Dict[str, CacheEntry], max_size: int) -> int:
        """Evict least recently used entries if cache is over size limit."""
        if len(cache) <= max_size:
            return 0

        # Sort by last accessed time (oldest first)
        entries = sorted(cache.items(), key=lambda x: x[1].last_accessed)
        to_remove = len(cache) - max_size

        for i in range(to_remove):
            key, _ = entries[i]
            del cache[key]
            self._evictions += 1

        return to_remove

    def _get_from_cache(self, cache: Dict[str, CacheEntry], key: str) -> Optional[Any]:
        """Get value from cache if it exists and is not expired."""
        entry = cache.get(key)
        if entry and not entry.is_expired():
            self._hits += 1
            return entry.access()
        elif entry:
            # Entry exists but is expired, remove it
            del cache[key]

        self._misses += 1
        return None

    def _set_cache(self, cache: Dict[str, CacheEntry], key: str, value: Any, ttl: float, max_size: int):
        """Set a value in cache with TTL and size management."""
        # Clean expired entries first
        self._cleanup_expired(cache)

        # Set new entry
        cache[key] = CacheEntry(value, ttl)

        # Evict LRU if over size limit
        self._evict_lru(cache, max_size)

    # Public API methods

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get cached embedding for text."""
        key = hashlib.md5(text.encode()).hexdigest()
        return self._get_from_cache(self._embedding_cache, key)

    def set_embedding(self, text: str, embedding: List[float]):
        """Cache embedding for text."""
        key = hashlib.md5(text.encode()).hexdigest()
        self._set_cache(self._embedding_cache, key, embedding, self._embedding_ttl, self._embedding_cache_size)

    def get_llm_response(self, prompt: str) -> Optional[str]:
        """Get cached LLM response for prompt."""
        key = hashlib.md5(prompt.encode()).hexdigest()
        return self._get_from_cache(self._llm_cache, key)

    def set_llm_response(self, prompt: str, response: str):
        """Cache LLM response for prompt."""
        key = hashlib.md5(prompt.encode()).hexdigest()
        self._set_cache(self._llm_cache, key, response, self._llm_ttl, self._llm_cache_size)

    def get_retriever(self, name: str) -> Optional[Any]:
        """Get cached retriever by name."""
        return self._get_from_cache(self._retriever_cache, name)

    def set_retriever(self, name: str, retriever: Any):
        """Cache retriever by name."""
        self._set_cache(self._retriever_cache, name, retriever, self._retriever_ttl, self._retriever_cache_size)

    def get(self, key: str, namespace: str = "") -> Optional[Any]:
        """Get value from general cache."""
        cache_key = self._get_cache_key(key, namespace)
        return self._get_from_cache(self._general_cache, cache_key)

    def set(self, key: str, value: Any, namespace: str = "", ttl: Optional[float] = None):
        """Set value in general cache."""
        cache_key = self._get_cache_key(key, namespace)
        ttl_value = ttl or self._general_ttl
        self._set_cache(self._general_cache, cache_key, value, ttl_value, self._general_cache_size)

    def clear(self, pattern: str = "*"):
        """Clear cache entries matching pattern."""
        if pattern == "*":
            self._embedding_cache.clear()
            self._llm_cache.clear()
            self._retriever_cache.clear()
            self._general_cache.clear()
            logger.info("All caches cleared")
        else:
            # Simple pattern matching
            for cache in [self._embedding_cache, self._llm_cache, self._retriever_cache, self._general_cache]:
                keys_to_remove = [k for k in cache.keys() if pattern in k]
                for key in keys_to_remove:
                    del cache[key]
            logger.info(f"Cleared {len(keys_to_remove)} entries matching '{pattern}'")

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_entries = (
            len(self._embedding_cache) + len(self._llm_cache) + len(self._retriever_cache) + len(self._general_cache)
        )
        hit_rate = self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0

        return {
            "embedding_cache": {
                "size": len(self._embedding_cache),
                "max_size": self._embedding_cache_size,
                "ttl_seconds": self._embedding_ttl,
            },
            "llm_cache": {"size": len(self._llm_cache), "max_size": self._llm_cache_size, "ttl_seconds": self._llm_ttl},
            "retriever_cache": {
                "size": len(self._retriever_cache),
                "max_size": self._retriever_cache_size,
                "ttl_seconds": self._retriever_ttl,
            },
            "general_cache": {
                "size": len(self._general_cache),
                "max_size": self._general_cache_size,
                "ttl_seconds": self._general_ttl,
            },
            "performance": {
                "total_entries": total_entries,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate * 100, 2),
                "evictions": self._evictions,
            },
        }

    async def cleanup_task(self):
        """Background task to periodically clean expired entries."""
        while True:
            await asyncio.sleep(300)  # Clean every 5 minutes

            with self._lock:
                total_cleaned = 0
                for cache in [self._embedding_cache, self._llm_cache, self._retriever_cache, self._general_cache]:
                    total_cleaned += self._cleanup_expired(cache)

                if total_cleaned > 0:
                    logger.debug(f"Cleaned {total_cleaned} expired cache entries")


# Global instance
cache_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    return cache_manager


# Convenience functions for backward compatibility
def get_embedding(text: str) -> Optional[List[float]]:
    """Get cached embedding (backward compatibility)."""
    return cache_manager.get_embedding(text)


def set_embedding(text: str, embedding: List[float]):
    """Cache embedding (backward compatibility)."""
    return cache_manager.set_embedding(text, embedding)


def get_llm_response(prompt: str) -> Optional[str]:
    """Get cached LLM response (backward compatibility)."""
    return cache_manager.get_llm_response(prompt)


def set_llm_response(prompt: str, response: str):
    """Cache LLM response (backward compatibility)."""
    return cache_manager.set_llm_response(prompt, response)
