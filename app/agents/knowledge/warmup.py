"""
Knowledge Agent Warm-up System

Pre-loads embeddings, caches, and connections for optimal performance.
"""

import asyncio
import time
import threading
from typing import List, Dict, Any, Optional
import logging

from app.settings import settings
from app.rag.embeddings import get_embeddings
from app.rag.vectorstore_milvus import MilvusVectorStore
from app.agents.knowledge.cache_manager import get_cache_manager
from app.agents.knowledge.retrieval_orchestrator import get_orchestrator
from app.agents.knowledge.context_builder import get_context_builder

logger = logging.getLogger(__name__)


class KnowledgeWarmup:
    """
    Intelligent warm-up system for Knowledge Agent.

    Features:
    - Pre-load common embeddings
    - Warm up vector store connections
    - Populate caches with frequent queries
    - Background warm-up for optimal performance
    """

    def __init__(self):
        self._cache_manager = get_cache_manager()
        self._orchestrator = get_orchestrator()
        self._context_builder = get_context_builder()
        self._is_warmed_up = False
        self._warmup_start_time = None
        self._warmup_thread = None

    def is_warmed_up(self) -> bool:
        """Check if warm-up is complete."""
        return self._is_warmed_up

    def get_warmup_status(self) -> Dict[str, Any]:
        """Get warm-up status and timing."""
        if self._warmup_start_time is None:
            return {"status": "not_started", "elapsed": 0}

        elapsed = time.time() - self._warmup_start_time
        return {
            "status": "warming_up" if not self._is_warmed_up else "complete",
            "elapsed": round(elapsed, 2),
            "is_warmed_up": self._is_warmed_up
        }

    def _warmup_common_embeddings(self) -> None:
        """Pre-compute embeddings for common queries."""
        logger.info("🔥 Warming up common embeddings...")

        common_queries = [
            "o que é maquininha",
            "como funciona o pix",
            "qual o preço da maquininha",
            "como fazer um boleto",
            "problemas com cartão",
            "taxas e tarifas",
            "suporte técnico",
            "abrir conta",
            "emprestimo pessoal",
            "pagamento online",
            "what is maquininha",
            "how does pix work",
            "card problems",
            "technical support",
            "account opening",
        ]

        try:
            embeddings = get_embeddings()
            if embeddings:
                cached_count = 0
                for query in common_queries:
                    try:
                        # Check if already cached
                        existing = self._cache_manager.get_embedding(query)
                        if existing:
                            logger.debug(f"   ℹ️ Embedding already cached for: '{query}'")
                            cached_count += 1
                            continue

                        # Compute and cache embedding
                        embedding = embeddings.embed_query(query)
                        if embedding and len(embedding) > 0:
                            self._cache_manager.set_embedding(query, embedding)
                            cached_count += 1
                            logger.debug(f"   ✅ Cached embedding for: '{query}'")
                        else:
                            logger.warning(f"   ⚠️ Empty embedding for: '{query}'")
                    except Exception as e:
                        logger.warning(f"   ⚠️ Failed to cache embedding for '{query}': {e}")

                logger.info(f"   🎯 Cached {cached_count}/{len(common_queries)} common embeddings")
            else:
                logger.warning("   ❌ Embeddings service not available - skipping embedding warm-up")

        except Exception as e:
            logger.error(f"   ❌ Common embeddings warm-up failed: {e}")
            logger.info("   ℹ️ Continuing with other warm-up steps...")

    def _warmup_vector_store(self) -> None:
        """Warm up vector store connections."""
        logger.info("🔥 Warming up vector store connections...")

        try:
            # Get embeddings for vector store
            embeddings = get_embeddings()
            if not embeddings:
                logger.warning("   ⚠️ Embeddings not available - vector store warm-up skipped")
                return

            # Create vector store retriever using proper method
            from app.rag.vectorstore_milvus import MilvusVectorStore
            retriever = MilvusVectorStore.connect_retriever(embedding=embeddings, k=3)

            if retriever:
                # Do a small test query to establish connection
                test_results = retriever.invoke("teste de aquecimento")
                logger.info(f"   ✅ Vector store connected (test returned {len(test_results)} results)")

                # Cache the retriever
                self._cache_manager.set("vector_retriever", retriever, "system", ttl=3600)
                logger.info("   ✅ Vector retriever cached successfully")
            else:
                logger.warning("   ⚠️ Vector retriever creation failed")

        except Exception as e:
            logger.error(f"   ❌ Vector store warm-up failed: {e}")
            logger.info("   ℹ️ Continuing with other warm-up steps...")

    def _warmup_faq_retriever(self) -> None:
        """Warm up FAQ retriever."""
        logger.info("🔥 Warming up FAQ retriever...")

        try:
            # Get embeddings for FAQ retriever
            embeddings = get_embeddings()
            if not embeddings:
                logger.warning("   ⚠️ Embeddings not available - FAQ retriever warm-up skipped")
                return

            # Create FAQ retriever connection
            faq_retriever = MilvusVectorStore.connect_faq_retriever(embedding=embeddings, k=2)
            if faq_retriever:
                # Do a small test query
                test_results = faq_retriever.invoke("teste de aquecimento")
                logger.info(f"   ✅ FAQ retriever connected (test returned {len(test_results)} results)")

                # Cache the FAQ retriever
                self._cache_manager.set("faq_retriever", faq_retriever, "system", ttl=3600)
                logger.info("   ✅ FAQ retriever cached successfully")
            else:
                logger.warning("   ⚠️ FAQ retriever creation failed")

        except Exception as e:
            logger.error(f"   ❌ FAQ retriever warm-up failed: {e}")
            logger.info("   ℹ️ Continuing with other warm-up steps...")

    def _warmup_retrieval_orchestrator(self) -> None:
        """Warm up retrieval orchestrator."""
        logger.info("🔥 Warming up retrieval orchestrator...")

        try:
            # Test orchestrator with a simple query
            result = self._orchestrator.orchestrate(
                question="teste de aquecimento",
                vector_k=1,
                enable_vector=True,  # Try both
                enable_faq=True
            )

            vector_success = result[0].success if len(result) > 0 else False
            faq_success = result[1].success if len(result) > 1 else False

            if vector_success or faq_success:
                logger.info(f"   ✅ Retrieval orchestrator warmed up (vector: {vector_success}, faq: {faq_success})")
                if vector_success and faq_success:
                    logger.info("   🎯 Both vector and FAQ retrieval working!")
                elif vector_success:
                    logger.info("   📄 Vector retrieval working (FAQ may need configuration)")
                elif faq_success:
                    logger.info("   ❓ FAQ retrieval working (Vector may need configuration)")
            else:
                logger.warning("   ⚠️ Retrieval orchestrator warm-up partial - retrievers may need configuration")
                logger.info("   💡 This is normal if RAG services are not fully configured")

        except Exception as e:
            logger.error(f"   ❌ Retrieval orchestrator warm-up failed: {e}")
            logger.info("   ℹ️ Continuing with other warm-up steps...")

    def _warmup_context_builder(self) -> None:
        """Warm up context builder."""
        logger.info("🔥 Warming up context builder...")

        try:
            # Test context building with minimal data
            from langchain_core.documents import Document
            test_docs = [Document(page_content="Teste de aquecimento do sistema", metadata={"source": "warmup"})]
            context, metadata = self._context_builder.build_context(
                question="teste",
                vector_docs=test_docs,
                faq_docs=[]
            )

            if context and len(context.strip()) > 0:
                logger.info(f"   ✅ Context builder warmed up (generated {len(context)} chars)")
            else:
                logger.warning("   ⚠️ Context builder warm-up failed - empty context")

        except Exception as e:
            logger.error(f"   ❌ Context builder warm-up failed: {e}")
            logger.info("   ℹ️ Continuing with other warm-up steps...")

    def _warmup_caches(self) -> None:
        """Pre-populate caches with common responses."""
        logger.info("🔥 Warming up response caches...")

        try:
            # Pre-cache some common LLM responses
            common_responses = {
                "greeting_cache": "Olá! Como posso ajudar você hoje?",
                "help_cache": "Estou aqui para ajudar com informações sobre produtos InfinitePay.",
                "product_cache": "Temos várias opções de maquininhas disponíveis."
            }

            for cache_key, response in common_responses.items():
                self._cache_manager.set_llm_response(cache_key, response)

            logger.info(f"   ✅ Pre-cached {len(common_responses)} common responses")

        except Exception as e:
            logger.error(f"   ❌ Cache warm-up failed: {e}")

    def warmup_sync(self) -> None:
        """Synchronous warm-up (blocking)."""
        logger.info("🚀 Starting Knowledge Agent warm-up (synchronous)...")
        self._warmup_start_time = time.time()

        try:
            # Execute warm-up steps in order
            self._warmup_common_embeddings()
            self._warmup_vector_store()
            self._warmup_faq_retriever()
            self._warmup_retrieval_orchestrator()
            self._warmup_context_builder()
            self._warmup_caches()

            warmup_time = time.time() - self._warmup_start_time
            self._is_warmed_up = True

            logger.info(f"🚀 Knowledge Agent warm-up completed in {warmup_time:.2f}s")
        except Exception as e:
            logger.error(f"❌ Warm-up failed: {e}")
            self._is_warmed_up = False

    def warmup_async(self) -> None:
        """Asynchronous warm-up (non-blocking)."""
        if self._warmup_thread and self._warmup_thread.is_alive():
            logger.info("🔄 Warm-up already in progress...")
            return

        logger.info("🚀 Starting Knowledge Agent warm-up (asynchronous)...")

        def _async_warmup():
            try:
                self.warmup_sync()
            except Exception as e:
                logger.error(f"Async warm-up failed: {e}")

        self._warmup_thread = threading.Thread(target=_async_warmup, daemon=True)
        self._warmup_thread.start()

    def warmup_lazy(self, question: str) -> None:
        """
        Lazy warm-up triggered by first query.

        Only warms up components that would be used for the specific question.
        """
        if self._is_warmed_up:
            return

        logger.info(f"🔥 Lazy warm-up triggered by: '{question[:50]}...'")

        try:
            # Quick warm-up of essential components
            self._warmup_start_time = time.time()

            # Always warm up embeddings (needed for any query)
            self._warmup_common_embeddings()

            # Warm up based on question type
            question_lower = question.lower()

            if any(word in question_lower for word in ["maquininha", "pix", "boleto", "cartão", "conta"]):
                # Product-related query - warm up vector store
                self._warmup_vector_store()
            elif any(word in question_lower for word in ["como", "qual", "quanto", "preço"]):
                # FAQ-style query - warm up FAQ retriever
                self._warmup_faq_retriever()

            # Mark as warmed for this type of query
            self._is_warmed_up = True
            warmup_time = time.time() - self._warmup_start_time

            logger.info(f"🚀 Knowledge Agent warm-up completed in {warmup_time:.2f}s")
        except Exception as e:
            logger.error(f"❌ Lazy warm-up failed: {e}")


# Global warm-up instance
_warmup_instance: Optional[KnowledgeWarmup] = None
_warmup_lock = threading.Lock()


def get_warmup_instance() -> KnowledgeWarmup:
    """Get global warm-up instance (singleton)."""
    global _warmup_instance

    if _warmup_instance is None:
        with _warmup_lock:
            if _warmup_instance is None:
                _warmup_instance = KnowledgeWarmup()

    return _warmup_instance


def warmup_knowledge_agent(async_mode: bool = True) -> None:
    """
    Convenience function to warm up the Knowledge Agent.

    Args:
        async_mode: If True, runs warm-up in background thread
    """
    warmup = get_warmup_instance()

    if async_mode:
        warmup.warmup_async()
    else:
        warmup.warmup_sync()


def check_warmup_status() -> Dict[str, Any]:
    """Check warm-up status."""
    warmup = get_warmup_instance()
    return warmup.get_warmup_status()


# Auto-warmup on import (background)
if settings.knowledge_warmup_enabled:
    logger.info("🔥 Auto-warmup enabled - starting background warm-up...")
    warmup_knowledge_agent(async_mode=True)
