"""
Knowledge Agent - Modular RAG Implementation

This module provides a highly optimized, modular Knowledge Agent for the Agent Swarm.
It features advanced caching, asynchronous execution, and granular LangSmith profiling.

Sub-modules:
- cache_manager: Centralized caching for embeddings, LLM responses, and retrievers
- cache: Simplified cache interface for knowledge agent components
- retrieval_orchestrator: Asynchronous retrieval orchestration
- context_builder: Intelligent context construction and optimization
- profiler: LangSmith profiling and performance monitoring
- config: Configuration management for the knowledge agent
- context: Context processing utilities
- llm: LLM interaction handling
- response: Response processing and formatting
- retrieval: Document retrieval handling
"""

# Lazy imports to avoid dependency issues during development
def __getattr__(name: str):
    """Lazy import for modules that may have dependencies."""
    if name == "knowledge_node":
        from .knowledge_node import knowledge_node
        return knowledge_node
    elif name == "knowledge_next":
        from .knowledge_node import knowledge_next
        return knowledge_next
    elif name == "CacheManager":
        from .cache_manager import CacheManager
        return CacheManager
    elif name == "KnowledgeCache":
        from .cache import KnowledgeCache
        return KnowledgeCache
    elif name == "get_knowledge_cache":
        from .cache import get_knowledge_cache
        return get_knowledge_cache
    elif name == "AsyncRetrievalOrchestrator":
        from .retrieval_orchestrator import AsyncRetrievalOrchestrator
        return AsyncRetrievalOrchestrator
    elif name == "ContextBuilder":
        from .context_builder import ContextBuilder
        return ContextBuilder
    elif name == "LangSmithProfiler":
        from .profiler import LangSmithProfiler
        return LangSmithProfiler
    elif name == "KnowledgeConfig":
        from .config import KnowledgeConfig
        return KnowledgeConfig
    elif name == "get_knowledge_config":
        from .config import get_knowledge_config
        return get_knowledge_config
    elif name == "ContextProcessor":
        from .context import ContextProcessor
        return ContextProcessor
    elif name == "get_context_processor":
        from .context import get_context_processor
        return get_context_processor
    elif name == "LLMHandler":
        from .llm import LLMHandler
        return LLMHandler
    elif name == "get_llm_handler":
        from .llm import get_llm_handler
        return get_llm_handler
    elif name == "ResponseProcessor":
        from .response import ResponseProcessor
        return ResponseProcessor
    elif name == "get_response_processor":
        from .response import get_response_processor
        return get_response_processor
    elif name == "RetrievalHandler":
        from .retrieval import RetrievalHandler
        return RetrievalHandler
    elif name == "get_retrieval_handler":
        from .retrieval import get_retrieval_handler
        return get_retrieval_handler
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "knowledge_node",
    "knowledge_next",
    "CacheManager",
    "KnowledgeCache",
    "get_knowledge_cache",
    "AsyncRetrievalOrchestrator",
    "ContextBuilder",
    "LangSmithProfiler",
    "KnowledgeConfig",
    "get_knowledge_config",
    "ContextProcessor",
    "get_context_processor",
    "LLMHandler",
    "get_llm_handler",
    "ResponseProcessor",
    "get_response_processor",
    "RetrievalHandler",
    "get_retrieval_handler",
]
