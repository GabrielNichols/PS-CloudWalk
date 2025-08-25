import time
import os
import pytest
from langsmith import traceable
from langchain_core.documents import Document
from app.settings import settings

from app.rag.embeddings import get_embeddings
from app.rag.vectorstore import Neo4jVectorStore
from app.rag.graph_retriever import graph_retrieve, recommend_params
from app.agents.knowledge import knowledge_node


QUESTION_PT = "Quais as taxas do cartão?"


def _has_card_fees_keywords(text: str) -> bool:
    t = (text or "").lower()
    return any(
        k in t for k in ["taxa", "taxas", "anuidade", "cartao", "cartão", "fees", "rate"]
    )  # noqa: D401,E501


@traceable(name="RetrievalCalibration_VectorOnly", metadata={"experiment": "retrieval-calibration"})
def test_vector_only_retrieval_card_fees():
    emb = get_embeddings()
    assert emb is not None, "Embeddings not configured for test"
    retriever = Neo4jVectorStore.connect_retriever(embedding=emb, k=3)
    assert retriever is not None, (
        "Vector retriever not available (no index/connection). Ensure Neo4j is reachable and the "
        "vector index 'infinitepay_chunks' exists (run: python -m app.rag.ingest)."
    )
    start = time.perf_counter()
    docs = retriever.invoke(QUESTION_PT)
    dur_ms = int((time.perf_counter() - start) * 1000)
    tops = [
        getattr(d, "metadata", {}).get("url") or getattr(d, "metadata", {}).get("source")
        for d in docs[:3]
    ]
    print(f"[VECTOR] ms={dur_ms} count={len(docs)} top_urls={tops}")
    assert isinstance(docs, list)
    assert len(docs) >= 1, f"no vector docs in {dur_ms}ms"
    combined = "\n".join([d.page_content for d in docs])
    assert _has_card_fees_keywords(combined)
    return {"mode": "real", "ms": dur_ms, "count": len(docs), "top_urls": tops}


@traceable(name="RetrievalCalibration_GraphOnly", metadata={"experiment": "retrieval-calibration"})
def test_graph_only_retrieval_card_fees():
    b, d = recommend_params(QUESTION_PT)
    start = time.perf_counter()
    try:
        rows, urls = graph_retrieve(QUESTION_PT, breadth=b, depth=d)
    except Exception as e:  # connection or index missing
        raise AssertionError(f"Graph retrieval unavailable: {e}")
    dur_ms = int((time.perf_counter() - start) * 1000)
    print(f"[GRAPH] ms={dur_ms} rows={len(rows)} urls={len(urls)} sample_urls={urls[:3]}")
    assert isinstance(rows, list)
    # allow zero in very sparse graphs but prefer at least one row
    assert len(rows) >= 1 or len(urls) >= 1, f"no graph rows/urls in {dur_ms}ms"
    # Prefer that one of the urls references the card page
    joined = " ".join(urls or [])
    assert ("/cartao" in joined) or (
        "cartao" in " ".join([r.get("entity", "").lower() for r in rows])
    )
    return {"ms": dur_ms, "rows": len(rows), "urls": urls[:3]}


@traceable(name="RetrievalCalibration_Hybrid", metadata={"experiment": "retrieval-calibration"})
def test_combined_hybrid_card_fees_confidence():
    out = knowledge_node({"message": QUESTION_PT, "locale": "pt-BR"})
    grounding = out.get("grounding", {})
    meta = out.get("meta", {})
    print(
        f"[HYBRID] mode={grounding.get('mode')} conf={grounding.get('confidence')} breadth={meta.get('breadth')}"
        f" depth={meta.get('depth')} vector_k={meta.get('vector_k')} latency_ms={meta.get('latency_ms')} urls={meta.get('urls_count')}"
    )
    # Should be using both when possible
    assert grounding.get("mode") in ("graph+vector", "none", "web", "placeholder")
    if grounding.get("mode") == "graph+vector":
        # Expect at least mid confidence; exact weighting depends on data
        assert grounding.get("confidence", 0) >= 0.5
    return {"mode": grounding.get("mode"), "confidence": grounding.get("confidence"), "meta": meta}
