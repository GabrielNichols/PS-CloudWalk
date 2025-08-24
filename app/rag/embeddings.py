from typing import Any
from app.settings import settings
from langchain_community.embeddings import OpenAIEmbeddings


def get_embeddings() -> Any:
    if settings.openai_api_key:
        # Newer langchain_openai uses api_key; community shim may accept openai_api_key. Use kwargs defensively.
        try:
            return OpenAIEmbeddings(
                model=settings.openai_embed_model, api_key=settings.openai_api_key
            )
        except TypeError:
            return OpenAIEmbeddings(model=settings.openai_embed_model)
    # Fallback placeholder: return None to signal not configured
    return None
