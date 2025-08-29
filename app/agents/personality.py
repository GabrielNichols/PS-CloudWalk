from typing import Dict, Any
from app.graph.memory import get_user_context_prompt, update_user_context
from app.agents.prompts import build_system_prompt, create_agent_messages
from app.agents.config import get_agent_config

from langsmith import traceable
from langchain_core.messages import HumanMessage


def _format_answer(answer: str, locale: str | None) -> str:
    """Format answer."""
    # Let the AI decide the language and format naturally
    # Remove any hardcoded prefixes that limit the AI's response
    lines = answer.strip()

    # Clean up any duplicate sources sections if they exist
    parts = lines.split("\nSources:")
    if len(parts) > 2:
        lines = parts[0] + "\nSources:" + parts[1]

    return lines


@traceable(name="PersonalityAgent", metadata={"agent": "PersonalityAgent", "tags": ["agent", "personality"]})
def personality_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Personality Agent.

    Role: Friendly Customer Service Assistant
    Goal: Provide warm, welcoming responses to user greetings and casual interactions
    """
    answer = (state.get("answer") if isinstance(state, dict) else None) or ""
    locale = state.get("locale") if isinstance(state, dict) else None
    user_id = state.get("user_id") if isinstance(state, dict) else None
    message = state.get("message") if isinstance(state, dict) else ""
    agent = (state.get("agent") if isinstance(state, dict) else None) or "PersonalityAgent"
    grounding = state.get("grounding") if isinstance(state, dict) else None
    meta = (state.get("meta") if isinstance(state, dict) else {}) or {}

    # Get user context for enhanced personality
    try:
        context_prompt = get_user_context_prompt(user_id) if user_id else ""
        if context_prompt:
            print(f"📋 PersonalityAgent: Using user context for {user_id}")
    except Exception as e:
        print(f"⚠️ PersonalityAgent: Failed to get user context: {e}")
        context_prompt = ""

    # Generate response using LangChain messages
    if not answer or answer.strip() == "":
        try:
            from openai import OpenAI
            from app.settings import settings

            if settings.openai_api_key:
                client = OpenAI(api_key=settings.openai_api_key)

                # Use structured message format
                messages = create_agent_messages(
                    agent_name="personality",
                    user_message=message,
                    locale=locale,
                    user_context=context_prompt
                )

                # Convert to OpenAI format for API call
                openai_messages = []
                for msg in messages:
                    if hasattr(msg, 'type'):
                        if msg.type == 'system':
                            openai_messages.append({"role": "system", "content": msg.content})
                        elif msg.type == 'human':
                            openai_messages.append({"role": "user", "content": msg.content})

                response = client.chat.completions.create(
                    model=settings.openai_model or "gpt-4o-mini",
                    messages=openai_messages,
                    temperature=0.8,  # Allow creativity for personality
                    max_tokens=150
                )

                answer = response.choices[0].message.content.strip()

        except Exception as e:
            print(f"⚠️ PersonalityAgent AI generation failed: {e}")
            # Minimal fallback
            if locale and str(locale).startswith("pt"):
                answer = "Olá! Como posso ajudar você hoje?"
            else:
                answer = "Hello! How can I help you today?"

    # Apply personality formatting with context awareness
    styled = _format_answer(answer, locale)

    # Update user context with final response
    if user_id:
        try:
            update_user_context(user_id, message, agent, styled)
        except Exception as e:
            print(f"⚠️ PersonalityAgent: Failed to update user context: {e}")

    return {
        "answer": styled,
        "agent": agent,
        "grounding": grounding,
        "meta": meta
    }
