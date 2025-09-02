from typing import Dict, Any
from app.tools.user_profile import get_user_info
from app.tools.ticketing import open_ticket
from app.graph.memory import get_user_context_prompt, update_user_context

from langsmith import traceable


@traceable(
    name="CustomerSupportAgent",
    metadata={"agent": "CustomerSupportAgent", "tags": ["agent", "support"]},
)
def support_node(state: Dict[str, Any]) -> Dict[str, Any]:
    user_id = (state.get("user_id") if isinstance(state, dict) else None) or "unknown"
    message = (state.get("message") if isinstance(state, dict) else None) or ""
    locale = (state.get("locale") if isinstance(state, dict) else None) or ""

    # Get user context for personalized support
    try:
        context_prompt = get_user_context_prompt(user_id)
        if context_prompt:
            print(f"📋 Support: Using user context for {user_id}")
    except Exception as e:
        print(f"⚠️ Support: Failed to get user context: {e}")
        context_prompt = ""

    # Get recent conversation context (short-term memory)
    conversation_context = ""
    if state.get("messages"):
        messages = state["messages"]
        # Get recent conversation history (last 5 exchanges)
        recent_messages = messages[-6:-1] if len(messages) > 6 else messages[:-1] if messages else []
        if recent_messages:
            context_parts = []
            for msg in recent_messages:
                if hasattr(msg, 'type'):
                    if msg.type == 'human':
                        context_parts.append(f"User: {msg.content}")
                    elif msg.type == 'ai':
                        context_parts.append(f"Assistant: {msg.content}")
            if context_parts:
                conversation_context = "\n".join(context_parts)
                print(f"📋 Support: Using recent conversation context ({len(context_parts)} messages)")

    # Get user profile information
    profile = get_user_info(user_id)

    # Do not hardcode categories via keywords; let downstream workflows classify if needed
    category = "general"

    # Create support ticket
    ticket = open_ticket(user_id, category, summary=message)

    # Localized, natural response (no rigid prefixes)
    is_pt = str(locale).lower().startswith("pt")
    if context_prompt and "returning user" in context_prompt:
        answer = (
            (f"Bem-vindo de volta! Já abri um chamado (#{ticket['id']}). "
             "Vamos considerar seus atendimentos anteriores e retornamos em seguida.")
            if is_pt
            else (f"Welcome back! I've opened a Support Ticket (#{ticket['id']}). "
                  "We'll review your previous interactions and get back to you shortly.")
        )
    else:
        answer = (
            (f"Abri um chamado (#{ticket['id']}). "
             "Nossa equipe entrará em contato em breve para ajudar.")
            if is_pt
            else (f"I've opened a Support Ticket (#{ticket['id']}). "
                  "Our team will contact you shortly to help resolve it.")
        )

    # Update user context with support interaction
    try:
        update_user_context(user_id, message, "CustomerSupportAgent", answer)
    except Exception as e:
        print(f"⚠️ Support: Failed to update user context: {e}")

    # Do not use 'sources' here to avoid frontend rendering as web sources
    grounding = {
        "mode": "tools",
        "artifacts": [
            {"type": "user_profile", "data": profile},
            {"type": "ticket", "data": ticket},
        ],
    }

    meta = {
        "agent": "CustomerSupportAgent",
        "ticket_id": ticket['id'],
        "category": category,
        "user_profile_status": profile.get("status", "unknown")
    }

    return {
        "answer": answer,
    "agent": "CustomerSupportAgent",
        "grounding": grounding,
        "meta": meta,
    }
