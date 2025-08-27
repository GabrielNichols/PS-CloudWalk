import time
import pytest
from langsmith import traceable
from app.rag.embeddings import get_embeddings
from app.rag.vectorstore_milvus import MilvusVectorStore
from langchain_core.documents import Document

@traceable(name="ZillizRetrieval.Performance", metadata={"test_type": "performance"})
def test_zilliz_chunks_retrieval_performance():
    """Test Zilliz chunks collection retrieval performance."""
    emb = get_embeddings()
    assert emb is not None, "Embeddings not configured for test"

    try:
        retriever = MilvusVectorStore.connect_retriever(embedding=emb, k=3)
    except RuntimeError as e:
        if "Zilliz" not in str(e):
            pytest.skip("Zilliz Cloud not configured")
        raise

    assert retriever is not None, "Zilliz retriever not available"

    # Test query
    question = "What are the fees of the Maquininha Smart?"
    start = time.perf_counter()
    docs = retriever.invoke(question)
    dur_ms = int((time.perf_counter() - start) * 1000)

    print(f"[ZILLIZ_CHUNKS] ms={dur_ms} count={len(docs)}")
    assert isinstance(docs, list)
    assert len(docs) >= 1, f"No documents retrieved in {dur_ms}ms"
    assert dur_ms < 1000, f"Retrieval too slow: {dur_ms}ms"

    return {"mode": "zilliz_chunks", "ms": dur_ms, "count": len(docs)}

@traceable(name="ZillizRetrieval.FAQ", metadata={"test_type": "faq_retrieval"})
def test_zilliz_faq_retrieval_performance():
    """Test Zilliz FAQ collection retrieval performance."""
    emb = get_embeddings()
    assert emb is not None, "Embeddings not configured for test"

    try:
        faq_retriever = MilvusVectorStore.connect_faq_retriever(embedding=emb, k=2)
    except RuntimeError as e:
        if "Zilliz" not in str(e):
            pytest.skip("Zilliz Cloud not configured")
        raise

    assert faq_retriever is not None, "Zilliz FAQ retriever not available"

    # Test FAQ query
    question = "What are the costs?"
    start = time.perf_counter()
    docs = faq_retriever.invoke(question)
    dur_ms = int((time.perf_counter() - start) * 1000)

    print(f"[ZILLIZ_FAQ] ms={dur_ms} count={len(docs)}")
    assert isinstance(docs, list)
    assert dur_ms < 500, f"FAQ retrieval too slow: {dur_ms}ms"

    return {"mode": "zilliz_faq", "ms": dur_ms, "count": len(docs)}

@traceable(name="ZillizRetrieval.Connection", metadata={"test_type": "connection"})
def test_zilliz_connection_stability():
    """Test Zilliz connection stability with multiple requests."""
    emb = get_embeddings()
    assert emb is not None, "Embeddings not configured for test"

    try:
        retriever = MilvusVectorStore.connect_retriever(embedding=emb, k=2)
    except RuntimeError as e:
        if "Zilliz" not in str(e):
            pytest.skip("Zilliz Cloud not configured")
        raise

    # Test multiple requests for connection stability
    question = "How does the card machine work?"
    times = []

    for i in range(3):  # Test 3 consecutive requests
        start = time.perf_counter()
        docs = retriever.invoke(question)
        dur_ms = int((time.perf_counter() - start) * 1000)
        times.append(dur_ms)

        assert len(docs) >= 0, f"Request {i+1} failed"

    avg_time = sum(times) / len(times)
    print(f"[ZILLIZ_STABILITY] avg_ms={avg_time:.1f} times={times}")

    # Connection should stabilize (first request might be slower)
    assert avg_time < 800, f"Average retrieval too slow: {avg_time:.1f}ms"
    assert max(times) < 1500, f"Max retrieval time too high: {max(times)}ms"

    return {"avg_ms": avg_time, "times": times}

@traceable(name="ZillizRetrieval.Content", metadata={"test_type": "content_quality"})
def test_zilliz_content_relevance():
    """Test content relevance from Zilliz retrieval."""
    emb = get_embeddings()
    assert emb is not None, "Embeddings not configured for test"

    try:
        retriever = MilvusVectorStore.connect_retriever(embedding=emb, k=3)
    except RuntimeError as e:
        if "Zilliz" not in str(e):
            pytest.skip("Zilliz Cloud not configured")
        raise

    # Test specific product query
    question = "What are the advantages of Tap to Pay?"
    docs = retriever.invoke(question)

    assert len(docs) > 0, "No documents retrieved for Tap to Pay query"

    # Check if retrieved content is relevant
    combined_content = " ".join([d.page_content for d in docs]).lower()
    relevance_keywords = ["tap to pay", "tap", "contactless", "nfc", "celular", "telefone"]

    has_relevance = any(keyword in combined_content for keyword in relevance_keywords)
    assert has_relevance, f"Retrieved content not relevant to query: {combined_content[:200]}..."

    return {"relevant": has_relevance, "doc_count": len(docs)}
