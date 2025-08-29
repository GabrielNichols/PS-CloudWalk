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

    # Get user context for personalized escalation
    try:
        context_prompt = get_user_context_prompt(user_id)
        if context_prompt:
            print(f"📋 Custom: Using user context for {user_id}")
    except Exception as e:
        print(f"⚠️ Custom: Failed to get user context: {e}")
        context_prompt = ""

    meta = {"agent": "CustomAgent"}
    base_meta: dict = {}
    try:
        conf = float((base_meta or {}).get("handoff_confidence") or 0.0)
    except Exception:
        conf = 0.0

    # Enhanced escalation logic with user context
    message_lower = message.lower()

    if any(k in message_lower for k in ["human", "help", "assist", "atendente", "pessoa"]):
        res = escalate_to_human(user_id, summary=message)

        # Personalized escalation message
        if context_prompt and "returning user" in context_prompt:
            answer = (
                "CustomAgent: I see you've reached out before. I've escalated your request to our senior support team. "
                "They'll have full context of your previous interactions and will reach out to you shortly."
            )
        else:
            answer = (
                "CustomAgent: I've escalated your request to our human support team. "
                "A specialist will review your inquiry and contact you shortly."
            )

        grounding = {"mode": "human/escalation", "tools": [res], "confidence": conf}

    else:
        # Slack notification with user context
        channel = settings.slack_default_channel or "#support"
        slack_message = f"User {user_id}: {message}"
        if context_prompt:
            slack_message += f"\n\nUser Context: {context_prompt[:200]}..."

        res = send_slack_message(channel, slack_message)

        answer = (
            "CustomAgent: I've notified our support team on Slack about your request. "
            "They're reviewing it now and will get back to you soon. Is there anything else I can help with?"
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
