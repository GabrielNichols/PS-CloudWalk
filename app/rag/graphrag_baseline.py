from __future__ import annotations

from typing import Any, Dict, Optional

from neo4j import GraphDatabase, Driver
from app.settings import settings


def _driver() -> Driver:
    uri = settings.neo4j_uri or (
        f"neo4j+s://{settings.aura_instanceid}.databases.neo4j.io"
        if settings.aura_instanceid
        else None
    )
    if not uri:
        raise RuntimeError("Neo4j URI not configured")
    if not settings.neo4j_username or not settings.neo4j_password:
        raise RuntimeError("Neo4j credentials not configured")
    return GraphDatabase.driver(uri, auth=(settings.neo4j_username, settings.neo4j_password))


class GraphRAGBaseline:
    """Thin wrapper around neo4j-graphrag to run a baseline side-by-side.

    Uses VectorRetriever by default; can be swapped to Hybrid/HyrbidCypher later.
    """

    def __init__(self, index_name: str = "infinitepay_chunks") -> None:
        self.index_name = index_name
        self._driver = _driver()
        self._llm: Any | None = None
        self._retriever: Any | None = None
        self._rag: Any | None = None

    def _ensure_components(self) -> None:
        if self._retriever is not None and self._llm is not None and self._rag is not None:
            return
        # Lazy dynamic import (avoids static import linter warnings if package not installed)
        import importlib

        mod_emb = importlib.import_module("neo4j_graphrag.embeddings")
        mod_llm = importlib.import_module("neo4j_graphrag.llm")
        mod_ret = importlib.import_module("neo4j_graphrag.retrievers")
        mod_gen = importlib.import_module("neo4j_graphrag.generation")

        GR_Emb = getattr(mod_emb, "OpenAIEmbeddings")
        GR_LLM = getattr(mod_llm, "OpenAILLM")
        GR_VectorRetriever = getattr(mod_ret, "VectorRetriever")
        GR_GraphRAG = getattr(mod_gen, "GraphRAG")

        embedder = GR_Emb(model=settings.openai_embed_model)
        self._retriever = GR_VectorRetriever(self._driver, self.index_name, embedder)
        self._llm = GR_LLM(model_name=(settings.openai_model_knowledge or settings.openai_model))
        self._rag = GR_GraphRAG(retriever=self._retriever, llm=self._llm)

    def search(self, query_text: str, top_k: int = 5, return_context: bool = True) -> Dict[str, Any]:
        self._ensure_components()
        assert self._rag is not None
        result = self._rag.search(
            query_text=query_text,
            retriever_config={"top_k": top_k},
            return_context=return_context,
        )
        return {
            "answer": getattr(result, "answer", None),
            "context": getattr(result, "context", None),
        }

    def close(self) -> None:
        try:
            self._driver.close()
        except Exception:
            pass
