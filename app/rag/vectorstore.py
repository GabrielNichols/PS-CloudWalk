from typing import Any, List, Optional
from app.settings import settings
from langchain_community.vectorstores.neo4j_vector import Neo4jVector
from langchain_community.vectorstores.neo4j_vector import SearchType
from langchain_core.documents import Document
from typing import Iterable


class Neo4jVectorStore:
    INDEX_NAME = "infinitepay_chunks"
    NODE_LABEL = "Chunk"
    KEYWORD_INDEX = "keyword"  # fulltext index for hybrid keyword expansion
    # Dedicated FAQ index
    FAQ_INDEX_NAME = "infinitepay_faqs"
    FAQ_NODE_LABEL = "FAQChunk"
    FAQ_KEYWORD_INDEX = "keyword_faq"

    def __init__(self, store: Neo4jVector | None = None) -> None:
        self.store = store

    @classmethod
    def from_documents(cls, docs: List[Document], embedding: Any) -> "Neo4jVectorStore":
        uri = cls.resolve_neo4j_uri()
        if not uri or not settings.neo4j_username or not settings.neo4j_password:
            return cls(None)
        store = Neo4jVector.from_documents(
            docs,
            embedding=embedding,
            url=uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
            database=settings.neo4j_database or "neo4j",
            node_label=cls.NODE_LABEL,
            index_name=cls.INDEX_NAME,
            search_type=SearchType.HYBRID,
            keyword_index_name=cls.KEYWORD_INDEX,
        )
        return cls(store)

    def as_retriever(self, k: int = 5):
        if not self.store:
            return None
        return self.store.as_retriever(search_kwargs={"k": k})

    @classmethod
    def index_in_batches(
        cls, docs: List[Document], embedding: Any, batch_size: int = 100
    ) -> "Neo4jVectorStore":
        uri = cls.resolve_neo4j_uri()
        if not uri or not settings.neo4j_username or not settings.neo4j_password:
            return cls(None)
        store: Optional[Neo4jVector] = None
        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]
            if not store:
                store = Neo4jVector.from_documents(
                    batch,
                    embedding=embedding,
                    url=uri,
                    username=settings.neo4j_username,
                    password=settings.neo4j_password,
                    database=settings.neo4j_database or "neo4j",
                    node_label=cls.NODE_LABEL,
                    index_name=cls.INDEX_NAME,
                    search_type=SearchType.HYBRID,
                    keyword_index_name=cls.KEYWORD_INDEX,
                )
            else:
                try:
                    store.add_documents(batch)
                except Exception:
                    # best-effort: skip bad batch
                    pass
        return cls(store)

    @classmethod
    def index_faqs_in_batches(
        cls, docs: List[Document], embedding: Any, batch_size: int = 100
    ) -> "Neo4jVectorStore":
        uri = cls.resolve_neo4j_uri()
        if not uri or not settings.neo4j_username or not settings.neo4j_password:
            return cls(None)
        store: Optional[Neo4jVector] = None
        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]
            if not store:
                store = Neo4jVector.from_documents(
                    batch,
                    embedding=embedding,
                    url=uri,
                    username=settings.neo4j_username,
                    password=settings.neo4j_password,
                    database=settings.neo4j_database or "neo4j",
                    node_label=cls.FAQ_NODE_LABEL,
                    index_name=cls.FAQ_INDEX_NAME,
                    search_type=SearchType.HYBRID,
                    keyword_index_name=cls.FAQ_KEYWORD_INDEX,
                )
            else:
                try:
                    store.add_documents(batch)
                except Exception:
                    pass
        return cls(store)

    @classmethod
    def connect_retriever(cls, embedding: Any, k: int = 5):
        uri = cls.resolve_neo4j_uri()
        if not uri or not settings.neo4j_username or not settings.neo4j_password:
            return None
        try:
            store = Neo4jVector.from_existing_index(
                embedding=embedding,
                url=uri,
                username=settings.neo4j_username,
                password=settings.neo4j_password,
                database=settings.neo4j_database or "neo4j",
                index_name=cls.INDEX_NAME,
                node_label=cls.NODE_LABEL,
                search_type=SearchType.HYBRID,
                keyword_index_name=cls.KEYWORD_INDEX,
            )
            return store.as_retriever(search_kwargs={"k": k})
        except Exception as e:  # expose cause to callers/tests
            # Provide actionable diagnostics for missing/invalid vector index
            raise RuntimeError(
                f"Failed to connect to existing Neo4j vector index '{cls.INDEX_NAME}' on label '{cls.NODE_LABEL}': {e}"
            )

    @classmethod
    def connect_faq_retriever(cls, embedding: Any, k: int = 5):
        uri = cls.resolve_neo4j_uri()
        if not uri or not settings.neo4j_username or not settings.neo4j_password:
            return None
        try:
            store = Neo4jVector.from_existing_index(
                embedding=embedding,
                url=uri,
                username=settings.neo4j_username,
                password=settings.neo4j_password,
                database=settings.neo4j_database or "neo4j",
                index_name=cls.FAQ_INDEX_NAME,
                node_label=cls.FAQ_NODE_LABEL,
                search_type=SearchType.HYBRID,
                keyword_index_name=cls.FAQ_KEYWORD_INDEX,
            )
            return store.as_retriever(search_kwargs={"k": k})
        except Exception as e:  # expose cause to callers/tests
            raise RuntimeError(
                f"Failed to connect to FAQ vector index '{cls.FAQ_INDEX_NAME}' on label '{cls.FAQ_NODE_LABEL}': {e}"
            )

    @staticmethod
    def resolve_neo4j_uri() -> Optional[str]:
        if settings.neo4j_uri:
            return settings.neo4j_uri
        if settings.aura_instanceid:
            return f"neo4j+s://{settings.aura_instanceid}.databases.neo4j.io"
        return None


class HeuristicVectorRetriever:
    """A clean, generic vector retriever that wraps Neo4jVector retriever and applies MMR.

    - No hard-coded URL preferences; relies on semantic similarity and diversity (MMR)
    - Trims to top-k and exposes a standard invoke(query)->List[Document] API
    """

    def __init__(self, base_retriever, k: int = 3, fetch_k: int = 8, mmr_lambda: float = 0.5):
        self.base = base_retriever
        self.k = k
        self.fetch_k = max(k, fetch_k)
        self.mmr_lambda = mmr_lambda

    def _embed(self, text: str) -> list[float]:
        # Use the same embeddings backend configured for the vector store
        from app.rag.embeddings import get_embeddings

        emb = get_embeddings()
        return emb.embed_query(text)

    def invoke(self, query: str):
        # fetch more than k, then apply MMR to enforce diversity
        docs: list[Document] = self.base.invoke(query)
        if not docs:
            return []
        pool = docs[: self.fetch_k]
        try:
            import numpy as np

            q_vec = np.array(self._embed(query))
            d_vecs = np.array([self._embed(d.page_content) for d in pool])

            def cos(a, b):
                return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

            selected: list[int] = []
            candidates = list(range(len(pool)))
            mmr = self.mmr_lambda
            while candidates and len(selected) < self.k:
                if not selected:
                    idx = max(candidates, key=lambda i: cos(q_vec, d_vecs[i]))
                    selected.append(idx)
                    candidates.remove(idx)
                    continue

                def diversity(i: int) -> float:
                    return max(cos(d_vecs[i], d_vecs[j]) for j in selected)

                idx = max(
                    candidates, key=lambda i: mmr * cos(q_vec, d_vecs[i]) - (1 - mmr) * diversity(i)
                )
                selected.append(idx)
                candidates.remove(idx)
            return [pool[i] for i in selected]
        except Exception:
            # Fallback: return top-k
            return pool[: self.k]


def connect_heuristic_vector_retriever(question: str, embedding: Any, k: int = 3):
    base = Neo4jVectorStore.connect_retriever(embedding=embedding, k=k)
    if not base:
        return None
    from app.settings import settings

    return HeuristicVectorRetriever(
        base,
        k=k,
        fetch_k=int(getattr(settings, "rag_fetch_k", 8) or 8),
        mmr_lambda=float(getattr(settings, "rag_mmr_lambda", 0.5) or 0.5),
    )
