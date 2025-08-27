"""
Configuration module for Knowledge Agent.

Centralizes configuration management for the knowledge agent components.
"""

from typing import Optional


class KnowledgeConfig:
    """Configuration class for Knowledge Agent components."""

    # Embedding configuration
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # Retrieval configuration
    vector_weight: float = 0.4
    faq_weight: float = 0.3
    graph_weight: float = 0.0

    # Context building configuration
    max_context_chars: int = 3000
    min_faq_chars: int = 600
    min_docs_chars: int = 800
    min_graph_chars: int = 600

    # Performance tuning
    enable_parallel: bool = True
    max_workers: int = 4
    complexity_threshold: int = 10

    # Caching configuration
    cache_embeddings: bool = True
    embedding_cache_ttl: int = 3600
    llm_cache_ttl: int = 300

    # Profiling configuration
    enable_profiling: bool = True
    profiling_detail_level: str = "medium"


# Global configuration instance
knowledge_config = KnowledgeConfig()


def get_knowledge_config() -> KnowledgeConfig:
    """Get the global knowledge configuration instance."""
    return knowledge_config