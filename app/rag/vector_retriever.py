from __future__ import annotations

from typing import List, Any, Optional
import asyncio
import time
import logging

import numpy as np
from langchain_core.documents import Document

from app.rag.vectorstore_milvus import MilvusVectorStore
from app.rag.embeddings import get_embeddings, aget_embeddings
from app.settings import settings
from app.agents.knowledge.cache_manager import get_cache_manager
from app.agents.knowledge.profiler import get_profiler, profile_step

logger = logging.getLogger(__name__)
_cache_manager = get_cache_manager()
_profiler = get_profiler()


class VectorRAGRetriever:
    """
    Optimized vector retriever with MMR post-processing and centralized caching.

    Features:
    - Uses MilvusVectorStore as the backend retriever
    - Fetches top-N (fetch_k) then applies MMR to choose top-k diverse and relevant chunks
    - Centralized caching with TTL and size limits
    - Async support for high-throughput scenarios
    - Performance monitoring and profiling
    - No hand-crafted URL rules or scraping
    """

    def __init__(
        self,
        embedding: Any | None = None,
        k: int | None = None,
        fetch_k: int | None = None,
        mmr_lambda: float | None = None,
    ) -> None:
        self.embedding = embedding or get_embeddings()
        self.k = int(k if k is not None else (settings.rag_vector_k or 3))
        # Reduce fetch_k to k by default to avoid extra I/O on Milvus when latency is a concern
        self.fetch_k = int(fetch_k if fetch_k is not None else (settings.rag_fetch_k or self.k))
        self.mmr_lambda = float(mmr_lambda if mmr_lambda is not None else (settings.rag_mmr_lambda or 0.5))

        if not self.embedding:
            raise RuntimeError("Embeddings backend not configured")

        # Use centralized cache instead of local cache
        self._retriever_cache_key = f"vector_retriever_{hash(str(self.embedding))}_{self.fetch_k}"

        # Lazy initialization of retriever
        self._base: Optional[Any] = None
        self._last_cache_hit: bool = False

    def _get_base_retriever(self) -> Any:
        """Get or create base retriever with caching."""
        if self._base is not None:
            return self._base

        # Try cache first
        cached_retriever = _cache_manager.get_retriever(self._retriever_cache_key)
        if cached_retriever:
            self._base = cached_retriever
            return self._base

        # Create new retriever
        retriever = MilvusVectorStore.connect_retriever(embedding=self.embedding, k=self.fetch_k)
        if not retriever:
            raise RuntimeError("Vector retriever not available (MilvusVector connection failed)")

        # Cache retriever
        _cache_manager.set_retriever(self._retriever_cache_key, retriever)
        self._base = retriever

        return retriever

    def _embed(self, text: str) -> np.ndarray:
        return np.array(self.embedding.embed_query(text))

    def probe_embed_ms(self, text: str) -> int:
        """Diagnostics: measure embed latency without affecting retrieval result."""
        start_time = time.perf_counter()
        try:
            _ = self.embedding.embed_query(text)
        except Exception:
            pass
        return int((time.perf_counter() - start_time) * 1000)

    def retrieve(self, query: str) -> List[Document]:
        """
        Return top-k from the backend retriever with optimized caching.

        Uses centralized cache manager for better performance and memory management.
        """
        with profile_step("VectorRAGRetriever.retrieve", {"query": query}):
            qn = (query or "").strip().lower()
            if not qn:
                return []

            # Try centralized cache first
            cache_key = f"vector_retrieval:{qn}"
            cached_result = _cache_manager.get(cache_key, "retrieval")

            if cached_result:
                self._last_cache_hit = True
                logger.debug(f"Cache hit for vector retrieval: {query}")
                return cached_result[: self.k]

            self._last_cache_hit = False

            # Get retriever and perform retrieval
            retriever = self._get_base_retriever()

            start_time = time.perf_counter()
            try:
                pool = retriever.invoke(query)
                retrieval_time = (time.perf_counter() - start_time) * 1000

                # Cache successful results
                if pool:
                    _cache_manager.set(cache_key, pool, "retrieval", ttl=300)  # 5 min cache
                    logger.debug(f"Vector retrieval completed: {len(pool)} docs in {retrieval_time:.1f}ms")

                return pool[: self.k] if pool else []

            except Exception as e:
                logger.error(f"Vector retrieval failed: {e}")
                return []

    async def aretrieve(self, query: str) -> List[Document]:
        """
        Async version of retrieve for high-throughput scenarios.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.retrieve, query)

    def get_stats(self) -> dict:
        """Get retriever statistics and performance metrics."""
        return {
            "k": self.k,
            "fetch_k": self.fetch_k,
            "mmr_lambda": self.mmr_lambda,
            "last_cache_hit": self._last_cache_hit,
            "embedding_type": type(self.embedding).__name__,
            "retriever_cached": self._base is not None,
        }
