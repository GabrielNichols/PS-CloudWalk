from typing import Dict, Any

from langsmith import traceable


def _format_answer(answer: str, locale: str | None) -> str:
    if locale and str(locale).startswith("pt"):
        prefix = "[pt-BR]"
    else:
        prefix = "[en]"
    # Avoid double 'Sources:' duplication; ensure single section at the end
    lines = answer.strip()
    # Normalize extra Sources duplicate suffix occurring in some runs
    # Keep the first 'Sources:' occurrence and drop subsequent duplicate headers
    parts = lines.split("\nSources:")
    if len(parts) > 2:
        lines = parts[0] + "\nSources:" + parts[1]
    return f"{prefix} {lines}"


@traceable(name="Personality", metadata={"agent": "Personality", "tags": ["agent", "personality"]})
def personality_node(state: Dict[str, Any]) -> Dict[str, Any]:
    answer = (state.get("answer") if isinstance(state, dict) else None) or ""
    locale = state.get("locale") if isinstance(state, dict) else None
    styled = _format_answer(answer, locale)
    agent = (state.get("agent") if isinstance(state, dict) else None) or "KnowledgeAgent"
    grounding = state.get("grounding") if isinstance(state, dict) else None
    meta = (state.get("meta") if isinstance(state, dict) else {}) or {}
    return {"answer": styled, "agent": agent, "grounding": grounding, "meta": meta}
