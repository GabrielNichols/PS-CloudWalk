#!/usr/bin/env python3
"""
Test file to verify that all imports in the knowledge module work correctly.
"""

def test_imports():
    """Test that all expected modules can be imported."""
    try:
        from .cache_manager import get_cache_manager, CacheManager
        from .context_builder import get_context_builder, ContextBuilder
        from .knowledge_node import knowledge_node, knowledge_next
        from .profiler import get_profiler, LangSmithProfiler
        from .retrieval_orchestrator import get_orchestrator, AsyncRetrievalOrchestrator

        print("✅ All imports successful!")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

if __name__ == "__main__":
    test_imports()
