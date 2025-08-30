"""
Clean Warm-up System - Optimized for Production
"""

import time
import logging
from typing import Any, Dict, Optional

from app.settings import settings

logger = logging.getLogger(__name__)

class KnowledgeWarmup:
    """Optimized warm-up system with minimal logging."""

    def __init__(self):
        self._is_warmed_up = False

    def is_warmed_up(self) -> bool:
        """Check if warm-up is complete."""
        return self._is_warmed_up

    def get_warmup_status(self) -> Dict[str, Any]:
        """Get warm-up status."""
        return {
            "status": "complete" if self._is_warmed_up else "not_started",
            "is_warmed_up": self._is_warmed_up
        }

def get_warmup_instance() -> KnowledgeWarmup:
    """Get global warm-up instance."""
    if not hasattr(get_warmup_instance, '_instance'):
        get_warmup_instance._instance = KnowledgeWarmup()
    return get_warmup_instance._instance

def initialize_warmup_system():
    """Initialize the warm-up system."""
    lazy_warmup_enabled = getattr(settings, 'knowledge_warmup_on_first_query', True)

    if lazy_warmup_enabled:
        try:
            from app.rag.embeddings import get_embeddings
            from app.agents.knowledge.cache_manager import get_cache_manager

            embeddings = get_embeddings()
            if embeddings:
                cache_manager = get_cache_manager()
                cache_manager.set("embeddings", embeddings, "system", ttl=3600)

                from app.rag.vectorstore_milvus import MilvusVectorStore

                try:
                    vector_retriever = MilvusVectorStore.connect_retriever(embedding=embeddings, k=3)
                    if vector_retriever:
                        cache_manager.set_retriever("vector_retriever_lazy", vector_retriever)
                except Exception:
                    pass

                try:
                    faq_retriever = MilvusVectorStore.connect_faq_retriever(embedding=embeddings, k=2)
                    if faq_retriever:
                        cache_manager.set_retriever("faq_retriever_lazy", faq_retriever)
                except Exception:
                    pass

                warmup = get_warmup_instance()
                warmup._is_warmed_up = True

        except Exception:
            pass

def _execute_zilliz_warmup_queries(embeddings):
    """Execute single dummy query to warm up Zilliz/Milvus database."""
    if not embeddings:
        return

    import os
    # Disable LangSmith tracing
    os.environ['LANGSMITH_TRACING'] = 'false'

    try:
        from app.rag.vectorstore_milvus import MilvusVectorStore
        # Single warm-up query
        retriever = MilvusVectorStore.connect_retriever(embedding=embeddings, k=1)
        if retriever:
            retriever.invoke("warmup")
    except Exception:
        pass
    finally:
        # Restore tracing
        os.environ['LANGSMITH_TRACING'] = 'true'

# Initialize on import if enabled
lazy_warmup_enabled = getattr(settings, 'knowledge_warmup_on_first_query', True)
if lazy_warmup_enabled:
    try:
        initialize_warmup_system()
    except Exception:
        pass
