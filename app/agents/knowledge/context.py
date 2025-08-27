"""
Context processing module for Knowledge Agent.

Handles context preparation and processing for LLM generation.
"""

from typing import List, Dict, Any, Optional
from .config import get_knowledge_config
from .cache import get_knowledge_cache


class ContextProcessor:
    """Processes and prepares context for LLM generation."""

    def __init__(self):
        self.config = get_knowledge_config()
        self.cache = get_knowledge_cache()

    def prepare_context(self, query: str, documents: List[Dict[str, Any]]) -> str:
        """
        Prepare context from retrieved documents.

        Args:
            query: The user's query
            documents: List of retrieved documents

        Returns:
            Formatted context string
        """
        if not documents:
            return ""

        context_parts = []
        for doc in documents:
            content = doc.get('page_content', doc.get('content', ''))
            if content:
                context_parts.append(content[:500])  # Limit content length

        return "\n\n".join(context_parts)

    def get_context_stats(self, context: str) -> Dict[str, Any]:
        """Get statistics about the context."""
        return {
            "char_count": len(context),
            "word_count": len(context.split()),
            "line_count": len(context.split('\n')),
        }


# Global instance
_context_processor: Optional[ContextProcessor] = None


def get_context_processor() -> ContextProcessor:
    """Get the global context processor instance."""
    global _context_processor
    if _context_processor is None:
        _context_processor = ContextProcessor()
    return _context_processor


def prepare_context(query: str, documents: List[Dict[str, Any]]) -> str:
    """Convenience function to prepare context."""
    return get_context_processor().prepare_context(query, documents)