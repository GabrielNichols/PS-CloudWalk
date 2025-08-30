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

    # Get enhanced user context including long-term memory
    context_prompt = ""
    long_term_memory = ""

    try:
        # Get basic context from database
        basic_context = get_user_context_prompt(user_id) if user_id else ""

        # Get long-term memory from state if available
        if state.get("user_context"):
            if isinstance(state["user_context"], dict) and state["user_context"].get("long_term_memory"):
                long_term_memory = state["user_context"]["long_term_memory"]
            elif isinstance(state["user_context"], str):
                long_term_memory = state["user_context"]

        # Combine contexts for more natural conversation
        if basic_context or long_term_memory:
            context_parts = []
            if basic_context:
                context_parts.append(f"User background: {basic_context}")
            if long_term_memory:
                context_parts.append(f"Recent conversation topics: {long_term_memory}")
            context_prompt = " ".join(context_parts)
            print(f"📋 PersonalityAgent: Using enhanced context for {user_id}")

            # Extract user name if available for personalization
            user_name = ""
            # Extract any relevant user information naturally from context
            # Let the LLM decide what information is important to remember
            # No hardcoded patterns - the AI should be free to remember anything

    except Exception as e:
        print(f"⚠️ PersonalityAgent: Failed to get context: {e}")
        user_name = ""

    # Generate response using LangChain messages with full session context
    if not answer or answer.strip() == "":
        try:
            from openai import OpenAI
            from app.settings import settings
            if settings.openai_api_key:
                client = OpenAI(api_key=settings.openai_api_key)

                # Build comprehensive conversation context from state messages (short-term memory)
                conversation_context = []
                if state.get("messages"):
                    messages = state["messages"]
                    # Get recent conversation history (last 10 exchanges for better context)
                    recent_messages = messages[-11:-1] if len(messages) > 11 else messages[:-1] if messages else []

                    for msg in recent_messages:
                        if hasattr(msg, 'type'):
                            if msg.type == 'human':
                                conversation_context.append({"role": "user", "content": msg.content})
                            elif msg.type == 'ai':
                                conversation_context.append({"role": "assistant", "content": msg.content})

                # Create enhanced system message with memory context and personalization
                system_content = f"""You are a friendly customer service assistant for InfinitePay.

GOAL: Provide warm, welcoming responses and maintain natural conversation flow with personalization.

BACKSTORY: You are a helpful assistant that remembers previous conversations, user preferences, and provides highly personalized service.

INSTRUCTIONS:
- Communicate naturally in the user's language
- CRITICAL: If the user asks about their name or personal information, FIRST check the PREVIOUS CONVERSATIONS section below
- If you find the information in PREVIOUS CONVERSATIONS, use it in your response
- Reference previous conversation topics when relevant to make responses more personal
- Don't repeat greetings if you've already greeted the user
- Use conversation context to provide relevant, personalized responses
- Be helpful, professional, and conversational
- Make the user feel recognized and valued by using their personal information
- Cite sources at the end as URLs under 'Sources:' when relevant

{f'PREVIOUS CONVERSATIONS: {context_prompt}' if context_prompt else ''}

RESPONSE GUIDELINES:
- If user says "Qual é o meu nome?" and you see "meu nome é João" in conversations, respond "Seu nome é João"
- If user says "O que eu faço?" and you see "sou desenvolvedor" in conversations, respond "Você é desenvolvedor"
- Always use the exact information from previous conversations when available

Continue the conversation naturally, making the user feel remembered and valued."""

                # Build messages for OpenAI API
                openai_messages = [
                    {"role": "system", "content": system_content}
                ]

                # Add recent conversation history
                openai_messages.extend(conversation_context)

                # Add current user message
                openai_messages.append({"role": "user", "content": message})

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

    # Set confidence for personality responses
    if not meta.get("confidence"):
        meta["confidence"] = 0.9  # High confidence for personality agent

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
