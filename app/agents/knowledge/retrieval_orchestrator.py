"""
Async Retrieval Orchestrator

Manages parallel and asynchronous retrieval operations for vector search and FAQ retrieval.
Optimizes execution based on available resources and query complexity.
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple, Callable, Union
import logging

from app.rag.vector_retriever import VectorRAGRetriever
from app.rag.vectorstore_milvus import MilvusVectorStore
from app.rag.embeddings import get_embeddings
from app.settings import settings
from app.agents.knowledge.cache_manager import get_cache_manager
from app.agents.knowledge.profiler import get_profiler, profile_step

logger = logging.getLogger(__name__)


class RetrievalResult:
    """Result of a retrieval operation."""

    def __init__(self, docs: List[Any], latency_ms: float, connect_ms: float, error: Optional[str] = None):
        self.docs = docs
        self.latency_ms = latency_ms
        self.connect_ms = connect_ms
        self.error = error
        self.success = error is None


class AsyncRetrievalOrchestrator:
    """
    Orchestrates asynchronous retrieval operations with intelligent parallelization.

    Features:
    - Smart parallel execution based on query complexity
    - Resource-aware thread pool management
    - Caching integration
    - Performance monitoring
    - Graceful degradation on failures
    """

    def __init__(self):
        self._cache_manager = get_cache_manager()
        self._profiler = get_profiler()

        # Thread pool configuration
        self._max_workers = getattr(settings, "retrieval_max_workers", 4)
        self._thread_pool: Optional[ThreadPoolExecutor] = None

        # Performance tuning
        self._complexity_threshold = getattr(settings, "query_complexity_threshold", 10)
        self._enable_parallel = getattr(settings, "enable_parallel_retrieval", True)

    def _get_thread_pool(self) -> ThreadPoolExecutor:
        """Get or create thread pool."""
        if self._thread_pool is None or self._thread_pool._shutdown:
            self._thread_pool = ThreadPoolExecutor(
                max_workers=self._max_workers, thread_name_prefix="RetrievalOrchestrator"
            )
        return self._thread_pool

    def _analyze_query_complexity(self, question: str) -> float:
        """Analyze query complexity to determine execution strategy."""
        words = question.split()
        word_count = len(words)

        # Factors that increase complexity
        complexity = word_count

        # Long words (technical terms)
        complexity += sum(1 for word in words if len(word) > 8)

        # Special characters (queries with symbols)
        complexity += question.count("?") + question.count("!")

        # Let AI assess complexity naturally from full context
        # No hardcoded keyword matching for complexity assessment

        return complexity

    def _should_run_parallel(self, question: str) -> bool:
        """Determine if query should run in parallel based on complexity."""
        if not self._enable_parallel:
            return False

        complexity = self._analyze_query_complexity(question)
        return complexity >= self._complexity_threshold

    def _execute_vector_sync(self, question: str, vector_k: int, emb_shared: Any) -> RetrievalResult:
        """Execute vector retrieval synchronously."""
        start_time = time.perf_counter()

        try:
            # Check if embeddings are available
            if not emb_shared:
                logger.warning("Vector retrieval skipped: embeddings not available")
                latency_ms = (time.perf_counter() - start_time) * 1000
                return RetrievalResult([], latency_ms, 0, "embeddings_not_available")

            # Try cache first
            cache_key = f"vector:{question}"
            cached_result = self._cache_manager.get(cache_key, "retrieval")
            if cached_result:
                return cached_result

            # Try pre-created lazy retriever first
            retriever_name = "vector_retriever_lazy"
            retriever = self._cache_manager.get_retriever(retriever_name)

            connect_start = time.perf_counter()
            if not retriever:
                # Fallback to main retriever
                retriever_name = "vector_main"
                retriever = self._cache_manager.get_retriever(retriever_name)

            if not retriever:
                # Last resort - create new retriever
                retriever = VectorRAGRetriever(embedding=emb_shared, k=vector_k)
                if retriever:
                    self._cache_manager.set_retriever(retriever_name, retriever)
                else:
                    logger.error("Vector retriever creation failed")
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    return RetrievalResult([], latency_ms, 0, "retriever_creation_failed")

            connect_ms = (time.perf_counter() - connect_start) * 1000

            # Execute retrieval
            docs = retriever.invoke(question)
            latency_ms = (time.perf_counter() - start_time) * 1000

            result = RetrievalResult(docs, latency_ms, connect_ms)

            # Cache result
            self._cache_manager.set(cache_key, result, "retrieval", ttl=300)  # 5 min cache

            return result

        except Exception as e:
            error_msg = f"Vector retrieval failed: {str(e)}"
            logger.error(error_msg)
            latency_ms = (time.perf_counter() - start_time) * 1000
            return RetrievalResult([], latency_ms, 0, error_msg)

    def _execute_faq_sync(self, question: str, emb_shared: Any) -> RetrievalResult:
        """Execute FAQ retrieval synchronously."""
        start_time = time.perf_counter()

        try:
            # Check if embeddings are available
            if not emb_shared:
                logger.warning("FAQ retrieval skipped: embeddings not available")
                latency_ms = (time.perf_counter() - start_time) * 1000
                return RetrievalResult([], latency_ms, 0, "embeddings_not_available")

            # Try cache first
            cache_key = f"faq:{question}"
            cached_result = self._cache_manager.get(cache_key, "retrieval")
            if cached_result:
                return cached_result

            # Try pre-created lazy retriever first
            retriever_name = "faq_retriever_lazy"
            retriever = self._cache_manager.get_retriever(retriever_name)

            connect_start = time.perf_counter()
            if not retriever:
                # Fallback to main retriever
                retriever_name = "faq_main"
                retriever = self._cache_manager.get_retriever(retriever_name)

            if not retriever:
                # Last resort - create new retriever
                retriever = MilvusVectorStore.connect_faq_retriever(embedding=emb_shared, k=2)
                if retriever:
                    self._cache_manager.set_retriever(retriever_name, retriever)
                else:
                    logger.error("FAQ retriever creation failed")
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    return RetrievalResult([], latency_ms, 0, "retriever_creation_failed")

            connect_ms = (time.perf_counter() - connect_start) * 1000

            # Execute retrieval
            docs = retriever.invoke(question)
            latency_ms = (time.perf_counter() - start_time) * 1000

            result = RetrievalResult(docs, latency_ms, connect_ms)

            # Cache result
            self._cache_manager.set(cache_key, result, "retrieval", ttl=300)  # 5 min cache

            return result

        except Exception as e:
            error_msg = f"FAQ retrieval failed: {str(e)}"
            logger.error(error_msg)
            latency_ms = (time.perf_counter() - start_time) * 1000
            return RetrievalResult([], latency_ms, 0, error_msg)

    def execute_parallel(
        self, question: str, vector_k: int = 3, emb_shared: Any = None
    ) -> Tuple[RetrievalResult, RetrievalResult]:
        """Execute vector and FAQ retrieval in parallel."""
        thread_pool = self._get_thread_pool()

        # Submit both tasks
        vector_future = thread_pool.submit(self._execute_vector_sync, question, vector_k, emb_shared)
        faq_future = thread_pool.submit(self._execute_faq_sync, question, emb_shared)

        # Wait for completion
        vector_result = vector_future.result()
        faq_result = faq_future.result()

        return vector_result, faq_result

    def execute_sequential(
        self,
        question: str,
        vector_k: int = 3,
        emb_shared: Any = None,
        enable_vector: bool = True,
        enable_faq: bool = True,
    ) -> Tuple[RetrievalResult, RetrievalResult]:
        """Execute vector and FAQ retrieval sequentially."""
        vector_result = RetrievalResult([], 0, 0)
        faq_result = RetrievalResult([], 0, 0)

        if enable_vector:
            vector_result = self._execute_vector_sync(question, vector_k, emb_shared)

        if enable_faq:
            faq_result = self._execute_faq_sync(question, emb_shared)

        return vector_result, faq_result

    def orchestrate(
        self,
        question: str,
        vector_k: int = 3,
        emb_shared: Any = None,
        enable_vector: bool = True,
        enable_faq: bool = True,
    ) -> Tuple[RetrievalResult, RetrievalResult]:
        """
        Main orchestration method that chooses execution strategy based on query complexity.

        Returns:
            Tuple of (vector_result, faq_result)
        """
        with profile_step(
            "RetrievalOrchestrator.orchestrate",
            {"question": question, "vector_k": vector_k, "enable_vector": enable_vector, "enable_faq": enable_faq},
        ):

            if not enable_vector and not enable_faq:
                return RetrievalResult([], 0, 0), RetrievalResult([], 0, 0)

            # Choose execution strategy
            if enable_vector and enable_faq and self._should_run_parallel(question):
                logger.debug(f"Running parallel retrieval for complex query: '{question}'")
                return self.execute_parallel(question, vector_k, emb_shared)
            else:
                logger.debug(f"Running sequential retrieval for query: '{question}'")
                return self.execute_sequential(question, vector_k, emb_shared, enable_vector, enable_faq)

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            "max_workers": self._max_workers,
            "complexity_threshold": self._complexity_threshold,
            "parallel_enabled": self._enable_parallel,
            "thread_pool_active": self._thread_pool is not None and not self._thread_pool._shutdown,
        }

    def shutdown(self):
        """Shutdown the orchestrator and cleanup resources."""
        if self._thread_pool and not self._thread_pool._shutdown:
            self._thread_pool.shutdown(wait=True)
            logger.info("RetrievalOrchestrator shutdown complete")


# Global instance
_orchestrator = AsyncRetrievalOrchestrator()


def get_orchestrator() -> AsyncRetrievalOrchestrator:
    """Get the global orchestrator instance."""
    return _orchestrator


# Convenience functions
def orchestrate_retrieval(
    question: str, vector_k: int = 3, emb_shared: Any = None, enable_vector: bool = True, enable_faq: bool = True
) -> Tuple[RetrievalResult, RetrievalResult]:
    """Convenience function for retrieval orchestration."""
    return _orchestrator.orchestrate(question, vector_k, emb_shared, enable_vector, enable_faq)


