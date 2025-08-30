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

    # Enhanced category detection based on message content
    message_lower = message.lower()
    if "transfer" in message_lower or "transação" in message_lower:
        category = "transfer"
    elif "sign in" in message_lower or "login" in message_lower or "entrar" in message_lower:
        category = "login"
    elif "password" in message_lower or "senha" in message_lower:
        category = "password_reset"
    elif "account" in message_lower or "conta" in message_lower:
        category = "account_issue"
    else:
        category = "general"

    # Create support ticket
    ticket = open_ticket(user_id, category, summary=message)

    # Personalized response based on user context
    if context_prompt and "returning user" in context_prompt:
        answer = (
            f"CustomerSupportAgent: Welcome back! I see you've contacted us before. "
            f"I've opened a new support ticket (#{ticket['id']}) for your {category} issue. "
            f"Our team will review your previous interactions and get back to you shortly."
        )
    else:
        answer = (
            f"CustomerSupportAgent: I've opened a support ticket (#{ticket['id']}) for your {category} issue. "
            f"Our support team will contact you shortly to help resolve this."
        )

    # Update user context with support interaction
    try:
        update_user_context(user_id, message, "CustomerSupportAgent", answer)
    except Exception as e:
        print(f"⚠️ Support: Failed to update user context: {e}")

    grounding = {
        "mode": "tools",
        "sources": [
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
