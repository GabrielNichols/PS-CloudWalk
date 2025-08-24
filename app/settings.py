from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    app_env: str = Field("dev", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    llm_provider: str = Field("openai", alias="LLM_PROVIDER")

    # OpenAI
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")
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

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()  # type: ignore[call-arg]
