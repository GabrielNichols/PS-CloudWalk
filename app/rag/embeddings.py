from typing import Any, List, Optional
import asyncio
import threading
from app.settings import settings
from langchain_community.embeddings import OpenAIEmbeddings

# Global instances
_EMB_SINGLETON: Any | None = None
_EMB_CACHED_SINGLETON: Any | None = None
_cache_manager = None


def _get_cache_manager():
    """Lazy import to avoid circular dependencies."""
    global _cache_manager
    if _cache_manager is None:
        from app.agents.knowledge.cache_manager import get_cache_manager
        _cache_manager = get_cache_manager()
    return _cache_manager


class OptimizedCachedEmbeddings:
    """
    Advanced cached embeddings with centralized cache management.

    Features:
    - Integration with CacheManager
    - TTL-based expiration
    - Size limits
    - Async support
    - Performance monitoring
    """

    def __init__(self, base: Any) -> None:
        self.base = base

    def embed_query(self, text: str) -> list[float]:
        """Get embeddings with caching."""
        if not text:
            return []

        # Try cache first
        cached = _get_cache_manager().get_embedding(text)
        if cached:
            return cached

        # Generate new embedding
        vec = self.base.embed_query(text)

        # Cache result with longer TTL since embeddings are deterministic
        _get_cache_manager().set_embedding(text, vec)

        return vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple documents."""
        return self.base.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        """Async version of embed_query."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed_query, text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Async version of embed_documents."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed_documents, texts)


def _build_openai_embeddings() -> Any | None:
    """Build OpenAI embeddings with optimized configuration."""
    if not settings.openai_api_key:
        return None

    try:
        # Prioritize faster models for better performance
        # text-embedding-3-small (1536 dims) is ~5x faster than text-embedding-3-large
        # text-embedding-ada-002 (1536 dims) is also very fast
        model_priority = [
            getattr(settings, "openai_embed_model_fast", None),
            "text-embedding-3-small",  # Fastest with good quality
            "text-embedding-ada-002",  # Good alternative
            settings.openai_embed_model,  # Fallback to configured model
        ]

        # Use first available model from priority list
        for model in model_priority:
            if model:
                try:
                    return OpenAIEmbeddings(model=model, api_key=settings.openai_api_key)
                except Exception:
                    continue

        # Final fallback
        return OpenAIEmbeddings(model=settings.openai_embed_model, api_key=settings.openai_api_key)

    except TypeError:
        model = getattr(settings, "openai_embed_model_fast", None) or settings.openai_embed_model
        return OpenAIEmbeddings(model=model)


def get_embeddings() -> Any:
    """
    Get optimized embeddings instance with centralized caching.

    Returns:
        OptimizedCachedEmbeddings instance or None if not configured
    """
    global _EMB_SINGLETON, _EMB_CACHED_SINGLETON

    # Return cached wrapper singleton if enabled (default True)
    use_cache = getattr(settings, "rag_embed_cache", True)

    if use_cache and _EMB_CACHED_SINGLETON is not None:
        return _EMB_CACHED_SINGLETON
    if not use_cache and _EMB_SINGLETON is not None:
        return _EMB_SINGLETON

    # Build base embeddings
    base = _EMB_SINGLETON or _build_openai_embeddings()
    _EMB_SINGLETON = base

    if not base:
        return None

    # Wrap with optimized caching
    if use_cache:
        _EMB_CACHED_SINGLETON = _EMB_CACHED_SINGLETON or OptimizedCachedEmbeddings(base)
        return _EMB_CACHED_SINGLETON

    return base


async def aget_embeddings() -> Any:
    """
    Async version of get_embeddings.

    Returns:
        OptimizedCachedEmbeddings instance or None if not configured
    """
    # For now, just return the sync version since embeddings are lightweight
    return get_embeddings()


# Convenience functions for backward compatibility
def embed_query(text: str) -> List[float]:
    """Convenience function for embedding a single query."""
    emb = get_embeddings()
    return emb.embed_query(text) if emb else []


def embed_documents(texts: List[str]) -> List[List[float]]:
    """Convenience function for embedding multiple documents."""
    emb = get_embeddings()
    return emb.embed_documents(texts) if emb else []


async def aembed_query(text: str) -> List[float]:
    """Async convenience function for embedding a single query."""
    emb = get_embeddings()
    if hasattr(emb, "aembed_query"):
        return await emb.aembed_query(text)
    return embed_query(text)


async def aembed_documents(texts: List[str]) -> List[List[float]]:
    """Async convenience function for embedding multiple documents."""
    emb = get_embeddings()
    if hasattr(emb, "aembed_documents"):
        return await emb.aembed_documents(texts)
    return embed_documents(texts)
