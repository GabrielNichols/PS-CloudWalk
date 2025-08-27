"""
Cache module for Knowledge Agent.

Provides a simplified interface to the cache manager for the knowledge agent components.
"""

from typing import Any, Optional, List, Dict


class KnowledgeCache:
    """Simplified cache interface for Knowledge Agent components."""

    def __init__(self):
        self._cache: Dict[str, Any] = {}

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get cached embedding for text."""
        return self._cache.get(f"embedding:{text}")

    def set_embedding(self, text: str, embedding: List[float]):
        """Cache embedding for text."""
        self._cache[f"embedding:{text}"] = embedding

    def get_llm_response(self, prompt: str) -> Optional[str]:
        """Get cached LLM response for prompt."""
        return self._cache.get(f"llm:{prompt}")

    def set_llm_response(self, prompt: str, response: str):
        """Cache LLM response for prompt."""
        self._cache[f"llm:{prompt}"] = response

    def get_retriever(self, name: str) -> Optional[Any]:
        """Get cached retriever by name."""
        return self._cache.get(f"retriever:{name}")

    def set_retriever(self, name: str, retriever: Any):
        """Cache retriever by name."""
        self._cache[f"retriever:{name}"] = retriever

    def get(self, key: str, namespace: str = "") -> Optional[Any]:
        """Get value from general cache."""
        cache_key = f"{namespace}:{key}" if namespace else key
        return self._cache.get(cache_key)

    def set(self, key: str, value: Any, namespace: str = "", ttl: Optional[float] = None):
        """Set value in general cache."""
        cache_key = f"{namespace}:{key}" if namespace else key
        self._cache[cache_key] = value

    def clear(self, pattern: str = "*"):
        """Clear cache entries matching pattern."""
        if pattern == "*":
            self._cache.clear()
        else:
            keys_to_remove = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "total_entries": len(self._cache),
            "embedding_entries": len([k for k in self._cache.keys() if k.startswith("embedding:")]),
            "llm_entries": len([k for k in self._cache.keys() if k.startswith("llm:")]),
        }


# Global instance
_knowledge_cache: Optional[KnowledgeCache] = None


def get_knowledge_cache() -> KnowledgeCache:
    """Get the global knowledge cache instance."""
    global _knowledge_cache
    if _knowledge_cache is None:
        _knowledge_cache = KnowledgeCache()
    return _knowledge_cache


# Convenience functions for backward compatibility
def get_embedding(text: str) -> Optional[List[float]]:
    """Get cached embedding (convenience function)."""
    return get_knowledge_cache().get_embedding(text)


def set_embedding(text: str, embedding: List[float]):
    """Cache embedding (convenience function)."""
    get_knowledge_cache().set_embedding(text, embedding)


def get_llm_response(prompt: str) -> Optional[str]:
    """Get cached LLM response (convenience function)."""
    return get_knowledge_cache().get_llm_response(prompt)


def set_llm_response(prompt: str, response: str):
    """Cache LLM response (convenience function)."""
    get_knowledge_cache().set_llm_response(prompt, response)