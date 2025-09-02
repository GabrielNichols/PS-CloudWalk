from typing import Dict, Any
from app.settings import settings
from app.graph.memory import get_user_context_prompt, update_user_context

from langsmith import traceable

from slack_sdk import WebClient


@traceable(name="CustomAgent")
def send_slack_message(channel: str, text: str) -> Dict[str, Any]:
    if not settings.slack_bot_token:
        return {"ok": False, "error": "SLACK_BOT_TOKEN missing"}
    client = WebClient(token=settings.slack_bot_token)
    resp = client.chat_postMessage(channel=channel or settings.slack_default_channel, text=text)
    # Slack SDK returns a Response object with data attr in tests; support both
    data = getattr(resp, "data", resp)
    try:
        ok = bool(data.get("ok"))  # type: ignore[call-arg]
    except Exception:
        ok = True  # type: ignore[assignment]
    return {"ok": ok, "ts": data.get("ts"), "channel": data.get("channel")}


def escalate_to_human(user_id: str, summary: str) -> Dict[str, Any]:
    return {"ok": True, "ticket_id": f"HUM-{user_id}", "summary": summary}


@traceable(name="CustomAgent", metadata={"agent": "CustomAgent", "tags": ["agent", "custom", "slack"]})
def custom_node(state: Dict[str, Any]) -> Dict[str, Any]:
    user_id = (state.get("user_id") if isinstance(state, dict) else None) or "unknown"
    message = (state.get("message") if isinstance(state, dict) else None) or ""
    locale = (state.get("locale") if isinstance(state, dict) else None) or ""

    # Get user context for personalized escalation
    context_prompt = ""
    try:
        context_prompt = get_user_context_prompt(user_id)
        if context_prompt:
            print(f"📋 Custom: Using user context for {user_id}")
            # Include user context in the escalation message for human agents
            if "returning user" in context_prompt or "interaction_count" in context_prompt:
                print("   👤 User has previous interactions - providing detailed context to human agent")
    except Exception as e:
        print(f"⚠️ Custom: Failed to get user context: {e}")
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
                print(f"📋 Custom: Using recent conversation context ({len(context_parts)} messages)")

    meta = {"agent": "CustomAgent"}
    base_meta: dict = {}
    try:
        conf = float((base_meta or {}).get("handoff_confidence") or 0.0)
    except Exception:
        conf = 0.0

    # Slack notification with enhanced user context (no keyword gating)
    channel = settings.slack_default_channel or "#support"
    slack_message = f"User {user_id}: {message}"

    if context_prompt:
        slack_message += f"\n\n👤 User Context: {context_prompt[:300]}..."
        if "returning user" in context_prompt:
            slack_message += "\n🔄 RETURNING USER - Check previous interactions"
        if "interaction_count" in context_prompt:
            slack_message += "\n📊 MULTIPLE INTERACTIONS - Review history"

    res = send_slack_message(channel, slack_message)

    answer = (
        "Avisei nossa equipe no Slack sobre o seu pedido. Estão analisando e te retornam em breve. Posso ajudar com mais algo?"
        if str(locale).lower().startswith("pt")
        else "I've notified our support team on Slack about your request. They're reviewing it now and will get back to you soon. Anything else I can help with?"
    )
    grounding = {"mode": "slack", "tools": [res], "confidence": conf}

    # Update user context with custom interaction
    try:
        update_user_context(user_id, message, "CustomAgent", answer)
    except Exception as e:
        print(f"⚠️ Custom: Failed to update user context: {e}")

    return {
        "answer": answer,
        "agent": "CustomAgent",
        "grounding": grounding,
        "meta": {**base_meta, **meta},
    }
