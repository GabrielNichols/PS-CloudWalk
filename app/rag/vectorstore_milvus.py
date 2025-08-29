from typing import Any, List, Optional

from app.settings import settings
from langchain_community.vectorstores import Milvus
from langchain_core.documents import Document
import logging

try:
    from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, utility

    MILVUS_NATIVE_AVAILABLE = True
except ImportError:
    MILVUS_NATIVE_AVAILABLE = False

logger = logging.getLogger(__name__)


class MilvusVectorStore:
    """Thin wrapper around langchain Milvus store for chunks and FAQ.

    Exposes connect_retriever for the chunks collection and connect_faq_retriever
    for the FAQ collection. Collections are created automatically with proper schemas.
    """

    @classmethod
    def _create_chunks_collection_schema(cls) -> CollectionSchema:
        """Create schema for chunks collection with proper field types."""
        if not MILVUS_NATIVE_AVAILABLE:
            raise RuntimeError("pymilvus package is required for schema creation")

        # Define fields for chunks collection
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=255, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=settings.milvus_dim),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="url", dtype=DataType.VARCHAR, max_length=2000),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=2000),
        ]

        return CollectionSchema(fields=fields, description="Document chunks with embeddings and metadata")

    @classmethod
    def _create_faq_collection_schema(cls) -> CollectionSchema:
        """Create schema for FAQ collection with proper field types."""
        if not MILVUS_NATIVE_AVAILABLE:
            raise RuntimeError("pymilvus package is required for schema creation")

        # Define fields for FAQ collection
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=255, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=settings.milvus_dim),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="url", dtype=DataType.VARCHAR, max_length=2000),
            FieldSchema(name="kind", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="answer", dtype=DataType.VARCHAR, max_length=1600),
            FieldSchema(name="product", dtype=DataType.VARCHAR, max_length=255),
        ]

        return CollectionSchema(fields=fields, description="FAQ entries with embeddings and metadata")

    @classmethod
    def _ensure_collection_exists(cls, collection_name: str, schema: CollectionSchema) -> None:
        """Ensure collection exists with proper schema and index."""
        if not MILVUS_NATIVE_AVAILABLE:
            return

        try:
            # Connect to Milvus
            connections = utility.connections
            if not connections.has_connection("default"):
                kwargs = cls._conn_kwargs()
                connections.connect("default", **kwargs)

            # Create collection if it doesn't exist
            if not utility.has_collection(collection_name):
                collection = Collection(collection_name, schema)

                # Create index for vector field
                index_params = {
                    "index_type": settings.milvus_index_type,
                    "metric_type": settings.milvus_metric,
                    "params": {"ef": settings.milvus_ef_search or 64},
                }
                collection.create_index("embedding", index_params)
                logger.info(f"Created collection '{collection_name}' with schema")

            # Load collection
            collection = Collection(collection_name)
            collection.load()

        except Exception as e:
            logger.warning(f"Could not ensure collection exists: {e}")

    @classmethod
    def _prepare_documents_for_insertion(
        cls, documents: List[Document]
    ) -> tuple[List[str], List[List[float]], List[dict]]:
        """Prepare documents for insertion by extracting texts, embeddings, and metadata."""
        texts = []
        metadatas = []

        for doc in documents:
            texts.append(doc.page_content)

            # Prepare metadata, ensuring all values are strings (no None values)
            metadata = {}
            if doc.metadata:
                for key, value in doc.metadata.items():
                    if value is not None:
                        metadata[key] = str(value)
                    # Skip None values completely - don't include them in metadata
            metadatas.append(metadata)

        return texts, metadatas

    @staticmethod
    def _conn_kwargs() -> dict:
        uri = settings.milvus_uri
        if uri:
            return {"uri": uri}
        host = settings.milvus_host or "localhost"
        port = settings.milvus_port or 19530
        secure = bool(settings.milvus_tls)
        user = settings.milvus_user
        password = settings.milvus_password
        kwargs = {"host": host, "port": port, "secure": secure}
        if user and password:
            kwargs.update({"user": user, "password": password})
        return kwargs

    @classmethod
    def connect_retriever(cls, embedding: Any, k: int = 3):
        try:
            # Validate embedding function
            if not embedding:
                logger.error("Vector retriever creation failed: embedding function is None")
                return None

            # Use Milvus with Zilliz Cloud configuration optimized for performance
            connection_args = {
                "uri": settings.zilliz_cloud_uri,
                "token": settings.zilliz_cloud_token,
                # Optimize connection pooling for better performance
                "pool_size": 10,
                "max_idle_time": 300,
                "timeout": 30,
            }

            store = Milvus(
                embedding_function=embedding,
                collection_name=settings.zilliz_cloud_collection_chunks,
                connection_args=connection_args,
                auto_id=True,
                # Let LangChain handle the schema
            )

            # Optimize search parameters for faster retrieval
            search_kwargs = {
                "k": k,
                "search_params": {
                    "metric_type": "COSINE",
                    "params": {"ef": getattr(settings, "zilliz_ef_search", 64)},  # Configurable HNSW search parameter
                },
            }

            return store.as_retriever(search_kwargs=search_kwargs)
        except Exception as e:
            logger.error(f"Failed to connect Zilliz Cloud chunks collection: {e}")
            return None

    @classmethod
    def connect_faq_retriever(cls, embedding: Any, k: int = 3):
        try:
            # Validate embedding function
            if not embedding:
                logger.error("FAQ retriever creation failed: embedding function is None")
                return None

            # Use Milvus with Zilliz Cloud configuration optimized for performance
            connection_args = {
                "uri": settings.zilliz_cloud_uri,
                "token": settings.zilliz_cloud_token,
                # Optimize connection pooling for better performance
                "pool_size": 10,
                "max_idle_time": 300,
                "timeout": 30,
            }

            store = Milvus(
                embedding_function=embedding,
                collection_name=settings.zilliz_cloud_collection_faq,
                connection_args=connection_args,
                auto_id=True,
                # Let LangChain handle the schema
            )

            # Optimize search parameters for faster retrieval
            search_kwargs = {
                "k": k,
                "search_params": {
                    "metric_type": "COSINE",
                    "params": {"ef": getattr(settings, "zilliz_ef_search", 64)},  # Configurable HNSW search parameter
                },
            }

            return store.as_retriever(search_kwargs=search_kwargs)
        except Exception as e:
            logger.error(f"Failed to connect Zilliz Cloud FAQ collection: {e}")
            return None

    @classmethod
    def index_in_batches(cls, documents: List[Document], embedding: Any, batch_size: int = 100) -> None:
        """Index documents in batches to the chunks collection using Zilliz Cloud."""
        try:
            # Use Milvus with Zilliz Cloud configuration
            store = Milvus(
                embedding_function=embedding,
                collection_name=settings.zilliz_cloud_collection_chunks,
                connection_args={"uri": settings.zilliz_cloud_uri, "token": settings.zilliz_cloud_token},
                auto_id=True,
                # Let LangChain create the collection with its default schema
            )

            # ZillizVectorStore handles collection creation and indexing automatically
            logger.info(f"Indexing {len(documents)} documents to Zilliz Cloud...")

            # Add documents to the vector store (it handles batching internally)
            store.add_documents(documents)

            logger.info(f"Successfully indexed {len(documents)} documents to Zilliz Cloud chunks collection")

        except Exception as e:
            logger.error(f"Error during indexing: {e}")
            raise RuntimeError(f"Failed to index documents to Milvus chunks collection: {e}")

    @classmethod
    def index_faqs_in_batches(cls, documents: List[Document], embedding: Any, batch_size: int = 100) -> None:
        """Index FAQ documents in batches to the FAQ collection using Zilliz Cloud."""
        try:
            # Use Milvus with Zilliz Cloud configuration
            store = Milvus(
                embedding_function=embedding,
                collection_name=settings.zilliz_cloud_collection_faq,
                connection_args={"uri": settings.zilliz_cloud_uri, "token": settings.zilliz_cloud_token},
                auto_id=True,
                # Specify field types to avoid auto-detection issues
                text_field="text",
                vector_field="vector",
            )

            # ZillizVectorStore handles collection creation and indexing automatically
            logger.info(f"Indexing {len(documents)} FAQ documents to Zilliz Cloud...")

            # Add documents to the vector store (it handles batching internally)
            store.add_documents(documents)

            logger.info(f"Successfully indexed {len(documents)} FAQ documents to Zilliz Cloud FAQ collection")

        except Exception as e:
            logger.error(f"Error during FAQ indexing: {e}")
            raise RuntimeError(f"Failed to index FAQ documents to Zilliz Cloud FAQ collection: {e}")
