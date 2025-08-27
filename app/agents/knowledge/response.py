"""
Response processing module for Knowledge Agent.

Handles response formatting, validation, and post-processing.
"""

from typing import Dict, Any, Optional
from .config import get_knowledge_config


class ResponseProcessor:
    """Processes and formats responses from the Knowledge Agent."""

    def __init__(self):
        self.config = get_knowledge_config()

    def format_response(self, response: str, locale: str = "en") -> str:
        """
        Format response based on locale and quality standards.

        Args:
            response: Raw response from LLM
            locale: User locale (en, pt-BR, etc.)

        Returns:
            Formatted response
        """
        # Clean up the response
        response = response.strip()

        # Add locale prefix
        if locale.startswith("pt"):
            prefix = "[pt-BR]"
        else:
            prefix = "[en]"

        # Ensure response has minimum quality
        if len(response) < 20:
            response = "I need more information to provide a complete answer."

        return f"{prefix} {response}"

    def add_sources(self, response: str, sources: list) -> str:
        """Add source citations to response."""
        if not sources:
            return response

        source_text = ", ".join(sources[:3])  # Limit to 3 sources
        return f"{response}\n\nSources: {source_text}"

    def validate_quality(self, response: str) -> Dict[str, Any]:
        """Validate response quality and return metrics."""
        return {
            "length": len(response),
            "has_sources": "Sources:" in response,
            "word_count": len(response.split()),
            "is_complete": not response.endswith("..."),
        }


# Global instance
_response_processor: Optional[ResponseProcessor] = None


def get_response_processor() -> ResponseProcessor:
    """Get the global response processor instance."""
    global _response_processor
    if _response_processor is None:
        _response_processor = ResponseProcessor()
    return _response_processor


def format_response(response: str, locale: str = "en") -> str:
    """Convenience function to format response."""
    return get_response_processor().format_response(response, locale)