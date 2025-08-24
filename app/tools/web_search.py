from typing import List, Dict, Any
import requests
from app.settings import settings


def web_search(query: str, k: int = 5) -> List[Dict[str, Any]]:
    if not settings.tavily_api_key:
        return []
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": settings.tavily_api_key, "query": query, "max_results": k},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
    except Exception:
        return []
