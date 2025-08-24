from typing import Dict, Any
from app.graph.helpers import sget

from langsmith import traceable


def _format_answer(answer: str, locale: str | None) -> str:
    if locale and locale.startswith("pt"):
        prefix = "[pt-BR]"
    else:
        prefix = "[en]"
    return f"{prefix} {answer}"


@traceable(name="Personality", metadata={"agent": "Personality", "tags": ["agent", "personality"]})
def personality_node(state: Dict[str, Any]) -> Dict[str, Any]:
    answer = sget(state, "answer") or ""
    locale = sget(state, "locale")
    styled = _format_answer(answer, locale)
    # Ensure carry-through of agent meta if present
    return {"answer": styled}
