"""
LLM interaction module for Knowledge Agent.

Handles LLM calls, response generation, and caching.
"""

from typing import Optional, Dict, Any
from .config import get_knowledge_config
from .cache import get_knowledge_cache


class LLMHandler:
    """Handles LLM interactions with caching and optimization."""

    def __init__(self):
        self.config = get_knowledge_config()
        self.cache = get_knowledge_cache()

    def generate_response(self, prompt: str, context: str = "") -> str:
        """
        Generate response using LLM with caching.

        Args:
            prompt: The prompt to send to LLM
            context: Additional context (optional)

        Returns:
            Generated response
        """
        # Check cache first
        cache_key = f"{prompt[:100]}:{hash(context)}"
        cached_response = self.cache.get_llm_response(cache_key)
        if cached_response:
            return cached_response

        # In a real implementation, this would call the LLM
        # For now, return a placeholder response
        response = f"KnowledgeAgent response for: {prompt[:50]}..."

        # Cache the response
        self.cache.set_llm_response(cache_key, response)

        return response

    def validate_response(self, response: str) -> bool:
        """Validate if response meets quality criteria."""
        min_length = getattr(self.config, 'min_answer_length', 40)
        return len(response.strip()) >= min_length


# Global instance
_llm_handler: Optional[LLMHandler] = None


def get_llm_handler() -> LLMHandler:
    """Get the global LLM handler instance."""
    global _llm_handler
    if _llm_handler is None:
        _llm_handler = LLMHandler()
    return _llm_handler


def generate_response(prompt: str, context: str = "") -> str:
    """Convenience function to generate LLM response."""
    return get_llm_handler().generate_response(prompt, context)