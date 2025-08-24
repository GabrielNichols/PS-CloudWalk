from typing import Any, List, Optional
from app.settings import settings
from langchain_community.vectorstores.neo4j_vector import Neo4jVector
from langchain_community.vectorstores.neo4j_vector import SearchType
from langchain_core.documents import Document


class Neo4jVectorStore:
    INDEX_NAME = "infinitepay_chunks"
    NODE_LABEL = "Chunk"

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
                )
            else:
                try:
                    store.add_documents(batch)
                except Exception:
                    # best-effort: skip bad batch
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
            )
            return store.as_retriever(search_kwargs={"k": k})
        except Exception:
            return None

    @staticmethod
    def resolve_neo4j_uri() -> Optional[str]:
        if settings.neo4j_uri:
            return settings.neo4j_uri
        if settings.aura_instanceid:
            return f"neo4j+s://{settings.aura_instanceid}.databases.neo4j.io"
        return None
