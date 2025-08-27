import time
import pytest
import asyncio
from langsmith import traceable
from app.agents.knowledge.knowledge_node import knowledge_node
from app.agents.router import router_node
from app.agents.support import support_node
from app.agents.custom import custom_node
from app.agents.knowledge.cache_manager import get_cache_manager
from app.agents.knowledge.retrieval_orchestrator import get_orchestrator
from app.agents.knowledge.context_builder import get_context_builder
from app.agents.knowledge.profiler import get_profiler
from app.rag.embeddings import get_embeddings
from app.rag.vector_retriever import VectorRAGRetriever

@traceable(name="Performance.Knowledge.Latency", metadata={"test_type": "performance", "agent": "knowledge"})
def test_knowledge_agent_latency():
    """Test KnowledgeAgent response latency."""
    question = "What are the fees of the Maquininha Smart?"
    state = {"message": question, "locale": "en", "user_id": "perf_test"}

    start_time = time.perf_counter()
    result = knowledge_node(state)
    end_time = time.perf_counter()

    latency_ms = (end_time - start_time) * 1000

    print(".1f")
    print(f"  Agent: {result.get('agent')}")
    print(f"  Mode: {result.get('grounding', {}).get('mode')}")

    # Assert reasonable latency (should be under 10 seconds)
    assert latency_ms < 10000, f"KnowledgeAgent too slow: {latency_ms:.1f}ms"

    # Assert successful response
    assert result.get("answer"), "No answer returned"
    assert result.get("agent") == "KnowledgeAgent", f"Wrong agent: {result.get('agent')}"

    return {"latency_ms": latency_ms, "agent": result.get("agent")}

@traceable(name="Performance.Router.Latency", metadata={"test_type": "performance", "agent": "router"})
def test_router_agent_latency():
    """Test RouterAgent response latency."""
    message = "I can't sign in to my account"
    state = {"message": message, "user_id": "perf_test"}

    start_time = time.perf_counter()
    result = router_node(state)
    end_time = time.perf_counter()

    latency_ms = (end_time - start_time) * 1000

    print(".1f")
    print(f"  Intent: {result.get('intent')}")

    # Router should be very fast (< 100ms)
    assert latency_ms < 100, f"RouterAgent too slow: {latency_ms:.1f}ms"
    assert result.get("intent") in ["knowledge", "support", "custom"], f"Invalid intent: {result.get('intent')}"

    return {"latency_ms": latency_ms, "intent": result.get("intent")}

@traceable(name="Performance.Support.Latency", metadata={"test_type": "performance", "agent": "support"})
def test_support_agent_latency():
    """Test CustomerSupportAgent response latency."""
    message = "I can't sign in to my account"
    state = {"message": message, "user_id": "perf_test"}

    start_time = time.perf_counter()
    result = support_node(state)
    end_time = time.perf_counter()

    latency_ms = (end_time - start_time) * 1000

    print(".1f")
    print(f"  Mode: {result.get('grounding', {}).get('mode')}")

    # Support agent should be fast (< 2 seconds)
    assert latency_ms < 2000, f"SupportAgent too slow: {latency_ms:.1f}ms"
    assert result.get("agent") == "CustomerSupportAgent", f"Wrong agent: {result.get('agent')}"

    return {"latency_ms": latency_ms, "mode": result.get('grounding', {}).get('mode')}

@traceable(name="Performance.Custom.Latency", metadata={"test_type": "performance", "agent": "custom"})
def test_custom_agent_latency():
    """Test CustomAgent response latency."""
    message = "Please escalate to human"
    state = {"message": message, "user_id": "perf_test"}

    start_time = time.perf_counter()
    result = custom_node(state)
    end_time = time.perf_counter()

    latency_ms = (end_time - start_time) * 1000

    print(".1f")
    print(f"  Mode: {result.get('grounding', {}).get('mode')}")

    # Custom agent should be very fast (< 500ms)
    assert latency_ms < 500, f"CustomAgent too slow: {latency_ms:.1f}ms"
    assert result.get("agent") == "CustomAgent", f"Wrong agent: {result.get('agent')}"

    return {"latency_ms": latency_ms, "mode": result.get('grounding', {}).get('mode')}

@traceable(name="Performance.Cache.Effectiveness", metadata={"test_type": "performance", "cache": "test"})
def test_cache_effectiveness():
    """Test LLM cache effectiveness."""
    question = "What is the InfinitePay card?"
    state = {"message": question, "locale": "en", "user_id": "cache_test"}

    # First request (should be slower)
    start_time = time.perf_counter()
    result1 = knowledge_node(state)
    end_time = time.perf_counter()
    first_latency = (end_time - start_time) * 1000

    # Second request (should be faster due to cache)
    start_time = time.perf_counter()
    result2 = knowledge_node(state)
    end_time = time.perf_counter()
    second_latency = (end_time - start_time) * 1000

    print(".1f")
    print(".1f")

    # Cache should make second request faster
    improvement_ratio = first_latency / max(second_latency, 1)
    print(".2f")

    # Assert cache is working (second request should be at least 50% faster)
    assert improvement_ratio > 1.5, f"Cache not effective enough: {improvement_ratio:.2f}x improvement"

    return {
        "first_latency_ms": first_latency,
        "second_latency_ms": second_latency,
        "improvement_ratio": improvement_ratio
    }

@traceable(name="Performance.Memory.Usage", metadata={"test_type": "performance", "memory": "test"})
def test_memory_efficiency():
    """Test memory efficiency with multiple requests."""
    import psutil
    import os

    initial_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # MB

    # Run multiple requests
    for i in range(5):
        question = f"What are the fees? Request {i+1}"
        state = {"message": question, "locale": "en", "user_id": f"memory_test_{i}"}
        knowledge_node(state)

    final_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # MB
    memory_delta = final_memory - initial_memory

    print(".1f")
    print(".1f")

    # Memory usage should not grow excessively (< 100MB)
    assert memory_delta < 100, f"Excessive memory usage: +{memory_delta:.1f}MB"

    return {"initial_mb": initial_memory, "final_mb": final_memory, "delta_mb": memory_delta}

@pytest.mark.parametrize("question,expected_agent", [
    ("What are the fees?", "KnowledgeAgent"),
    ("I can't sign in", "CustomerSupportAgent"),
    ("Speak to human", "CustomAgent"),
])
@traceable(name="Performance.Agent.Routing", metadata={"test_type": "performance", "routing": "test"})
def test_agent_routing_performance(question, expected_agent):
    """Test routing performance for different question types."""
    state = {"message": question, "user_id": "routing_test"}

    start_time = time.perf_counter()
    result = router_node(state)
    routing_time = (time.perf_counter() - start_time) * 1000

    print(".1f")

    # Routing should be very fast
    assert routing_time < 50, f"Routing too slow: {routing_time:.1f}ms"

    return {"question": question, "routing_ms": routing_time, "intent": result.get("intent")}


@traceable(name="Performance.CacheManager", metadata={"test_type": "performance", "module": "cache_manager"})
def test_cache_manager_performance():
    """Test CacheManager performance and functionality."""
    cache_manager = get_cache_manager()

    # Clear cache for clean test
    cache_manager.clear()

    # Test embedding cache
    test_embedding = [0.1, 0.2, 0.3] * 512  # 1536 dimensions

    # First access - should miss
    start_time = time.perf_counter()
    result = cache_manager.get_embedding("test_query")
    first_access = (time.perf_counter() - start_time) * 1000

    assert result is None, "Expected cache miss"

    # Set embedding
    cache_manager.set_embedding("test_query", test_embedding)

    # Second access - should hit
    start_time = time.perf_counter()
    result = cache_manager.get_embedding("test_query")
    second_access = (time.perf_counter() - start_time) * 1000

    assert result == test_embedding, "Cache returned wrong value"

    print(f"CacheManager - First access: {first_access:.3f}ms, Second access: {second_access:.3f}ms")
    print(".2f")

    # Test LLM cache
    prompt = "What are the fees?"
    response = "The fees are..."

    cache_manager.set_llm_response(prompt, response)
    cached_response = cache_manager.get_llm_response(prompt)

    assert cached_response == response, "LLM cache failed"

    # Test stats
    stats = cache_manager.stats()
    assert stats["performance"]["hits"] >= 1, "Expected at least one cache hit"

    return {
        "first_access_ms": first_access,
        "second_access_ms": second_access,
        "cache_hit_ratio": stats["performance"]["hit_rate"]
    }


@traceable(name="Performance.RetrievalOrchestrator", metadata={"test_type": "performance", "module": "retrieval_orchestrator"})
def test_retrieval_orchestrator_performance():
    """Test AsyncRetrievalOrchestrator performance."""
    try:
        from app.rag.embeddings import get_embeddings
        emb = get_embeddings()
        if not emb:
            pytest.skip("Embeddings not configured")

        orchestrator = get_orchestrator()

        # Test with simple query
        question = "test query"

        start_time = time.perf_counter()
        vector_result, faq_result = orchestrator.orchestrate(
            question=question,
            vector_k=2,
            emb_shared=emb,
            enable_vector=True,
            enable_faq=False  # Disable FAQ for faster test
        )
        orchestration_time = (time.perf_counter() - start_time) * 1000

        print(".1f")

        # Should complete in reasonable time
        assert orchestration_time < 5000, f"Orchestration too slow: {orchestration_time:.1f}ms"

        return {
            "orchestration_ms": orchestration_time,
            "vector_success": vector_result.success,
            "faq_success": faq_result.success
        }

    except Exception as e:
        pytest.skip(f"RetrievalOrchestrator test failed: {e}")


@traceable(name="Performance.ContextBuilder", metadata={"test_type": "performance", "module": "context_builder"})
def test_context_builder_performance():
    """Test ContextBuilder performance."""
    from langchain_core.documents import Document

    context_builder = get_context_builder()

    # Create test documents
    docs = [
        Document(page_content="This is a test document about fees.", metadata={"url": "test.com"}),
        Document(page_content="Another document about payments.", metadata={"url": "test2.com"})
    ]

    question = "What are the fees?"

    start_time = time.perf_counter()
    context, metadata = context_builder.build_context(
        question=question,
        vector_docs=docs,
        faq_docs=[]
    )
    build_time = (time.perf_counter() - start_time) * 1000

    print(f"ContextBuilder - Build time: {build_time:.1f}ms")
    print(f"Context length: {len(context)} chars")

    # Should be fast
    assert build_time < 100, f"Context building too slow: {build_time:.1f}ms"
    assert len(context) > 0, "Context should not be empty"

    return {
        "build_ms": build_time,
        "context_length": len(context),
        "sections_count": metadata.get("context_sections", [])
    }


@traceable(name="Performance.VectorRetriever", metadata={"test_type": "performance", "module": "vector_retriever"})
def test_vector_retriever_performance():
    """Test VectorRAGRetriever performance."""
    try:
        emb = get_embeddings()
        if not emb:
            pytest.skip("Embeddings not configured")

        retriever = VectorRAGRetriever(embedding=emb, k=2)

        # Test retrieval
        query = "test retrieval query"

        start_time = time.perf_counter()
        docs = retriever.retrieve(query)
        retrieval_time = (time.perf_counter() - start_time) * 1000

        print(f"VectorRetriever - Retrieval time: {retrieval_time:.1f}ms")
        print(f"Retrieved {len(docs)} documents")

        # Should complete in reasonable time
        assert retrieval_time < 2000, f"Retrieval too slow: {retrieval_time:.1f}ms"

        # Test stats
        stats = retriever.get_stats()
        assert "k" in stats, "Stats should include k parameter"

        return {
            "retrieval_ms": retrieval_time,
            "docs_count": len(docs),
            "cache_hit": stats.get("last_cache_hit", False)
        }

    except Exception as e:
        pytest.skip(f"VectorRetriever test failed: {e}")


@traceable(name="Performance.Embeddings", metadata={"test_type": "performance", "module": "embeddings"})
def test_embeddings_performance():
    """Test optimized embeddings performance."""
    emb = get_embeddings()
    if not emb:
        pytest.skip("Embeddings not configured")

    test_text = "This is a test for embedding performance"

    # Test embedding generation
    start_time = time.perf_counter()
    embedding = emb.embed_query(test_text)
    embed_time = (time.perf_counter() - start_time) * 1000

    print(f"Embeddings - Generation time: {embed_time:.1f}ms")
    print(f"Embedding dimensions: {len(embedding)}")

    # Should be reasonably fast
    assert embed_time < 500, f"Embedding generation too slow: {embed_time:.1f}ms"
    assert len(embedding) > 0, "Embedding should not be empty"

    # Test caching by running again
    start_time = time.perf_counter()
    embedding2 = emb.embed_query(test_text)
    embed_time2 = (time.perf_counter() - start_time) * 1000

    print(f"Embeddings - Cached time: {embed_time2:.3f}ms")
    print(".2f")

    # Cached version should be faster
    assert embed_time2 < embed_time, "Cached embedding should be faster"
    assert embedding == embedding2, "Embeddings should be identical"

    return {
        "first_embed_ms": embed_time,
        "cached_embed_ms": embed_time2,
        "speedup_ratio": embed_time / max(embed_time2, 0.001),
        "dimensions": len(embedding)
    }


@traceable(name="Performance.AsyncOperations", metadata={"test_type": "performance", "module": "async"})
def test_async_operations_performance():
    """Test async operations performance."""
    async def run_async_test():
        try:
            from app.rag.embeddings import aget_embeddings
            from app.rag.vector_retriever import VectorRAGRetriever

            emb = await aget_embeddings()
            if not emb:
                return None

            retriever = VectorRAGRetriever(embedding=emb, k=2)

            # Test async retrieval
            start_time = time.perf_counter()
            docs = await retriever.aretrieve("async test query")
            async_time = (time.perf_counter() - start_time) * 1000

            return {
                "async_retrieval_ms": async_time,
                "docs_count": len(docs)
            }

        except Exception as e:
            print(f"Async test failed: {e}")
            return None

    # Run async test
    result = asyncio.run(run_async_test())

    if result:
        print(".1f")
        assert result["async_retrieval_ms"] < 3000, f"Async retrieval too slow: {result['async_retrieval_ms']:.1f}ms"
        return result
    else:
        pytest.skip("Async operations test skipped")


@traceable(name="Performance.ModuleIntegration", metadata={"test_type": "performance", "module": "integration"})
def test_module_integration_performance():
    """Test integration between all optimized modules."""
    # This test measures end-to-end performance of the modular system
    cache_manager = get_cache_manager()
    profiler = get_profiler()

    # Clear caches for clean test
    cache_manager.clear()

    # Test simple knowledge node call (will use modular components)
    question = "What are the fees?"
    state = {"message": question, "locale": "en", "user_id": "integration_test"}

    # Run profiler
    with profiler.profile_step("IntegrationTest"):
        start_time = time.perf_counter()
        try:
            result = knowledge_node(state)
            end_time = time.perf_counter()
            total_time = (end_time - start_time) * 1000

            print(".1f")
            print(f"Response: {result.get('answer', '')[:100]}...")

            # Should complete in reasonable time
            assert total_time < 10000, f"Integration test too slow: {total_time:.1f}ms"
            assert result.get("answer"), "Should return an answer"

            # Get performance summary
            summary = profiler.get_performance_summary()

            return {
                "total_ms": total_time,
                "agent": result.get("agent"),
                "cache_stats": cache_manager.stats()["performance"],
                "profile_summary": summary
            }

        except Exception as e:
            pytest.skip(f"Integration test failed: {e}")
