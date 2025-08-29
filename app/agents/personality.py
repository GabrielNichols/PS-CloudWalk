from typing import Dict, Any
from app.graph.memory import get_user_context_prompt, update_user_context

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
    user_id = state.get("user_id") if isinstance(state, dict) else None
    agent = (state.get("agent") if isinstance(state, dict) else None) or "KnowledgeAgent"
    grounding = state.get("grounding") if isinstance(state, dict) else None
    meta = (state.get("meta") if isinstance(state, dict) else {}) or {}

    # Get user context for enhanced personality
    try:
        context_prompt = get_user_context_prompt(user_id) if user_id else ""
        if context_prompt:
            print(f"📋 Personality: Using user context for {user_id}")
    except Exception as e:
        print(f"⚠️ Personality: Failed to get user context: {e}")
        context_prompt = ""

    # Apply personality formatting with context awareness
    styled = _format_answer(answer, locale)

    # Update user context with final response
    if user_id:
        try:
            update_user_context(user_id, "", agent, styled)
        except Exception as e:
            print(f"⚠️ Personality: Failed to update user context: {e}")

    return {
        "answer": styled,
        "agent": agent,
        "grounding": grounding,
        "meta": meta
    }
