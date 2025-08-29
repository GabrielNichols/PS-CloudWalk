from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    app_env: str = Field("dev", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    llm_provider: str = Field("openai", alias="LLM_PROVIDER")

    # OpenAI
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")
    # Optional faster model for latency-sensitive paths (e.g., KnowledgeAgent)
    openai_model_fast: str | None = Field(default=None, alias="OPENAI_MODEL_FAST")
    # Optional per-agent override
    openai_model_knowledge: str | None = Field(default=None, alias="OPENAI_MODEL_KNOWLEDGE")
    openai_embed_model: str = Field("text-embedding-3-large", alias="OPENAI_EMBED_MODEL")
    # Optional faster embedding model (defaults to small for better performance)
    openai_embed_model_fast: str | None = Field("text-embedding-3-small", alias="OPENAI_EMBED_MODEL_FAST")
    # Token caps for KnowledgeAgent requests
    openai_max_tokens_knowledge: int | None = Field(default=None, alias="OPENAI_MAX_TOKENS_KNOWLEDGE")
    openai_max_tokens_knowledge_retry: int | None = Field(default=None, alias="OPENAI_MAX_TOKENS_KNOWLEDGE_RETRY")

    # Web search
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")

    # Firecrawl (extract)
    firecrawl_api_key: str | None = Field(default=None, alias="FIRECRAWL_API_KEY")

    # Supabase / Postgres
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    # LangSmith / LangChain tracing
    langsmith_api_key: str | None = Field(default=None, alias="LANGSMITH_API_KEY")
    langchain_tracing_v2: str | None = Field(default=None, alias="LANGCHAIN_TRACING_V2")
    langchain_project: str | None = Field(default=None, alias="LANGCHAIN_PROJECT")
    langsmith_tracing: str | None = Field(default=None, alias="LANGSMITH_TRACING")
    langsmith_project: str | None = Field(default=None, alias="LANGSMITH_PROJECT")
    langsmith_endpoint: str | None = Field(default=None, alias="LANGSMITH_ENDPOINT")
    # Compatibility with legacy var names
    langchain_endpoint: str | None = Field(default=None, alias="LANGCHAIN_ENDPOINT")

    # Handoff threshold
    handoff_threshold: float | None = Field(default=None, alias="HANDOFF_THRESHOLD")

    # Rate limiting
    rate_limit_per_minute: int = Field(60, alias="RATE_LIMIT_PER_MINUTE")

    # Knowledge Agent Warm-up
    knowledge_warmup_enabled: bool = Field(True, alias="KNOWLEDGE_WARMUP_ENABLED")
    knowledge_warmup_async: bool = Field(True, alias="KNOWLEDGE_WARMUP_ASYNC")
    knowledge_warmup_on_first_query: bool = Field(True, alias="KNOWLEDGE_WARMUP_ON_FIRST_QUERY")

    # Slack integration (CustomAgent)
    slack_bot_token: str | None = Field(default=None, alias="SLACK_BOT_TOKEN")
    slack_default_channel: str = Field("#support", alias="SLACK_DEFAULT_CHANNEL")

    # Retrieval knobs
    rag_vector_k: int = Field(3, alias="RAG_VECTOR_K")
    rag_vector_k_fees: int = Field(2, alias="RAG_VECTOR_K_FEES")
    rag_vector_weight: float = Field(0.4, alias="RAG_VECTOR_WEIGHT")
    rag_graph_weight: float = Field(0.0, alias="RAG_GRAPH_WEIGHT")  # Disabled since we removed graph

    rag_max_context_chars: int = Field(2000, alias="RAG_MAX_CONTEXT_CHARS")
    rag_fetch_k: int = Field(8, alias="RAG_FETCH_K")
    rag_mmr_lambda: float = Field(0.5, alias="RAG_MMR_LAMBDA")
    rag_sources_max: int = Field(3, alias="RAG_SOURCES_MAX")
    rag_fulltext_min_score: float = Field(0.0, alias="RAG_FULLTEXT_MIN_SCORE")
    # Index-time chunking
    rag_index_chunk_chars: int = Field(900, alias="RAG_INDEX_CHUNK_CHARS")
    rag_index_chunk_overlap: int = Field(120, alias="RAG_INDEX_CHUNK_OVERLAP")
    # Runtime caches and warmup
    rag_embed_cache: bool = Field(True, alias="RAG_EMBED_CACHE")
    rag_vector_cache_ttl: int = Field(60, alias="RAG_VECTOR_CACHE_TTL")
    rag_warmup_on_start: bool = Field(False, alias="RAG_WARMUP_ON_START")

    # Knowledge agent cache
    knowledge_cache_ttl: int | None = Field(default=60, alias="KNOWLEDGE_CACHE_TTL")

    # Vector backend: milvus only
    vector_backend: str = Field("milvus", alias="VECTOR_BACKEND")

    # Zilliz Cloud settings (Milvus Managed)
    zilliz_cloud_uri: str = Field(..., alias="ZILLIZ_CLOUD_URI")
    zilliz_cloud_token: str = Field(..., alias="ZILLIZ_CLOUD_TOKEN")
    zilliz_cloud_collection_chunks: str = Field("ps_chunks", alias="ZILLIZ_CLOUD_COLLECTION_CHUNKS")
    zilliz_cloud_collection_faq: str = Field("ps_faq", alias="ZILLIZ_CLOUD_COLLECTION_FAQ")
    zilliz_cloud_dim: int = Field(1536, alias="ZILLIZ_CLOUD_DIM")  # Optimized for speed with text-embedding-3-small
    zilliz_cloud_metric: str = Field("COSINE", alias="ZILLIZ_CLOUD_METRIC")

    # Legacy Milvus settings (optional for backward compatibility)
    milvus_uri: str | None = Field(None, alias="MILVUS_URI")
    milvus_host: str | None = Field(None, alias="MILVUS_HOST")
    milvus_port: int | None = Field(None, alias="MILVUS_PORT")
    milvus_user: str | None = Field(None, alias="MILVUS_USER")
    milvus_password: str | None = Field(None, alias="MILVUS_PASSWORD")
    milvus_tls: bool = Field(False, alias="MILVUS_TLS")
    milvus_collection_chunks: str = Field("ps_chunks", alias="MILVUS_COLLECTION_CHUNKS")
    milvus_collection_faq: str = Field("ps_faq", alias="MILVUS_COLLECTION_FAQ")
    milvus_dim: int = Field(1536, alias="MILVUS_DIM")  # Optimized for speed with text-embedding-3-small
    milvus_metric: str = Field("COSINE", alias="MILVUS_METRIC")
    milvus_index_type: str = Field("HNSW", alias="MILVUS_INDEX_TYPE")
    milvus_ef_search: int | None = Field(default=64, alias="MILVUS_EF_SEARCH")

    # Zilliz Cloud performance tuning
    zilliz_ef_search: int = Field(64, alias="ZILLIZ_EF_SEARCH")  # HNSW search parameter for speed vs accuracy tradeoff

    # Feature toggles
    enable_vector: bool = Field(True, alias="ENABLE_VECTOR")
    enable_faq: bool = Field(True, alias="ENABLE_FAQ")

    # Cache Manager Configuration
    embedding_cache_size: int = Field(1000, alias="EMBEDDING_CACHE_SIZE")
    llm_cache_size: int = Field(500, alias="LLM_CACHE_SIZE")
    retriever_cache_size: int = Field(10, alias="RETRIEVER_CACHE_SIZE")
    general_cache_size: int = Field(100, alias="GENERAL_CACHE_SIZE")
    embedding_cache_ttl: int = Field(3600, alias="EMBEDDING_CACHE_TTL")
    llm_cache_ttl: int = Field(300, alias="LLM_CACHE_TTL")
    retriever_cache_ttl: int = Field(600, alias="RETRIEVER_CACHE_TTL")
    general_cache_ttl: int = Field(300, alias="GENERAL_CACHE_TTL")

    # Retrieval Orchestrator Configuration
    retrieval_max_workers: int = Field(4, alias="RETRIEVAL_MAX_WORKERS")
    enable_parallel_retrieval: bool = Field(True, alias="ENABLE_PARALLEL_RETRIEVAL")
    query_complexity_threshold: int = Field(10, alias="QUERY_COMPLEXITY_THRESHOLD")

    # Context Builder Configuration
    rag_min_chars_faq: int = Field(600, alias="RAG_MIN_CHARS_FAQ")
    rag_min_chars_docs: int = Field(800, alias="RAG_MIN_CHARS_DOCS")
    rag_min_chars_graph: int = Field(600, alias="RAG_MIN_CHARS_GRAPH")

    # LangSmith Profiling Configuration
    enable_profiling: bool = Field(True, alias="ENABLE_PROFILING")
    profiling_detail_level: str = Field("medium", alias="PROFILING_DETAIL_LEVEL")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
