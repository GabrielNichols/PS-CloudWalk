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

    # Web search
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")

    # Firecrawl (extract)
    firecrawl_api_key: str | None = Field(default=None, alias="FIRECRAWL_API_KEY")

    # Neo4j
    neo4j_uri: str | None = Field(default=None, alias="NEO4J_URI")
    neo4j_username: str | None = Field(default=None, alias="NEO4J_USERNAME")
    neo4j_password: str | None = Field(default=None, alias="NEO4J_PASSWORD")
    neo4j_database: str | None = Field("neo4j", alias="NEO4J_DATABASE")
    aura_instanceid: str | None = Field(default=None, alias="AURA_INSTANCEID")
    aura_instancename: str | None = Field(default=None, alias="AURA_INSTANCENAME")

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

    # Slack integration (CustomAgent)
    slack_bot_token: str | None = Field(default=None, alias="SLACK_BOT_TOKEN")
    slack_default_channel: str = Field("#support", alias="SLACK_DEFAULT_CHANNEL")

    # Retrieval knobs
    rag_vector_k: int = Field(3, alias="RAG_VECTOR_K")
    rag_vector_k_fees: int = Field(2, alias="RAG_VECTOR_K_FEES")
    rag_graph_weight: float = Field(0.6, alias="RAG_GRAPH_WEIGHT")
    rag_vector_weight: float = Field(0.4, alias="RAG_VECTOR_WEIGHT")
    rag_max_context_chars: int = Field(2000, alias="RAG_MAX_CONTEXT_CHARS")
    rag_fetch_k: int = Field(8, alias="RAG_FETCH_K")
    rag_mmr_lambda: float = Field(0.5, alias="RAG_MMR_LAMBDA")
    rag_sources_max: int = Field(3, alias="RAG_SOURCES_MAX")
    rag_fulltext_min_score: float = Field(0.0, alias="RAG_FULLTEXT_MIN_SCORE")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()  # type: ignore[call-arg]
