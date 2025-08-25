from __future__ import annotations

from typing import List, Any

import numpy as np
from langchain_core.documents import Document

from app.rag.vectorstore import Neo4jVectorStore
from app.rag.embeddings import get_embeddings
from app.settings import settings


class VectorRAGRetriever:
    """Generic vector retriever with MMR post-processing.

    - Uses Neo4jVectorStore (HYBRID) as the backend retriever
    - Fetches top-N (fetch_k) then applies MMR to choose top-k diverse and relevant chunks
    - No hand-crafted URL rules or scraping
    """

    def __init__(self, embedding: Any | None = None, k: int | None = None, fetch_k: int | None = None, mmr_lambda: float | None = None) -> None:
        self.embedding = embedding or get_embeddings()
        self.k = int(k if k is not None else (settings.rag_vector_k or 3))
        self.fetch_k = int(fetch_k if fetch_k is not None else (settings.rag_fetch_k or max(8, self.k)))
        self.mmr_lambda = float(mmr_lambda if mmr_lambda is not None else (settings.rag_mmr_lambda or 0.5))
        if not self.embedding:
            raise RuntimeError("Embeddings backend not configured")
        self._base = Neo4jVectorStore.connect_retriever(embedding=self.embedding, k=self.fetch_k)
        if not self._base:
            raise RuntimeError("Vector retriever not available (Neo4jVector connection failed)")

    def _embed(self, text: str) -> np.ndarray:
        return np.array(self.embedding.embed_query(text))

    def retrieve(self, query: str) -> List[Document]:
        """Return top-k from the backend retriever without extra embedding calls.

        This avoids per-document embedding (which was causing multi-second latency)
        and relies on the Neo4j HYBRID search ranking.
        """
        pool: List[Document] = self._base.invoke(query)
        if not pool:
            return []
        return pool[: self.k]
