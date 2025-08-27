"""
Retrieval module for Knowledge Agent.

Handles document retrieval from vector stores and knowledge bases.
"""

from typing import List, Dict, Any, Optional
from .config import get_knowledge_config
from .cache import get_knowledge_cache


class RetrievalHandler:
    """Handles document retrieval with caching and optimization."""

    def __init__(self):
        self.config = get_knowledge_config()
        self.cache = get_knowledge_cache()

    def retrieve_documents(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents for a query.

        Args:
            query: Search query
            top_k: Number of documents to retrieve

        Returns:
            List of retrieved documents
        """
        # Check cache first
        cache_key = f"retrieval:{query}:{top_k}"
        cached_docs = self.cache.get(cache_key, "retrieval")
        if cached_docs:
            return cached_docs

        # In a real implementation, this would search vector stores
        # For now, return placeholder documents
        documents = [
            {
                "content": f"Document about {query}",
                "source": "knowledge_base",
                "score": 0.9
            }
        ]

        # Cache results
        self.cache.set(cache_key, documents, "retrieval", ttl=300)

        return documents

    def retrieve_faq(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
        Retrieve relevant FAQ entries for a query.

        Args:
            query: Search query
            top_k: Number of FAQ entries to retrieve

        Returns:
            List of retrieved FAQ entries
        """
        # Check cache first
        cache_key = f"faq:{query}:{top_k}"
        cached_faqs = self.cache.get(cache_key, "retrieval")
        if cached_faqs:
            return cached_faqs

        # In a real implementation, this would search FAQ vector store
        # For now, return placeholder FAQ entries
        faqs = [
            {
                "question": f"What is {query}?",
                "answer": f"This is information about {query}",
                "source": "faq_database"
            }
        ]

        # Cache results
        self.cache.set(cache_key, faqs, "retrieval", ttl=300)

        return faqs

    def get_retrieval_stats(self) -> Dict[str, Any]:
        """Get retrieval performance statistics."""
        return {
            "cache_stats": self.cache.stats(),
            "config": {
                "vector_weight": self.config.vector_weight,
                "faq_weight": self.config.faq_weight,
                "enable_parallel": self.config.enable_parallel,
            }
        }


# Global instance
_retrieval_handler: Optional[RetrievalHandler] = None


def get_retrieval_handler() -> RetrievalHandler:
    """Get the global retrieval handler instance."""
    global _retrieval_handler
    if _retrieval_handler is None:
        _retrieval_handler = RetrievalHandler()
    return _retrieval_handler


def retrieve_documents(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Convenience function to retrieve documents."""
    return get_retrieval_handler().retrieve_documents(query, top_k)


def retrieve_faq(query: str, top_k: int = 2) -> List[Dict[str, Any]]:
    """Convenience function to retrieve FAQ entries."""
    return get_retrieval_handler().retrieve_faq(query, top_k)