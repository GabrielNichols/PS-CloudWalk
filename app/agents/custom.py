from typing import Dict, Any
from app.graph.helpers import sget, sget_meta
from app.settings import settings

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
        ok = True
    return {"ok": ok, "ts": data.get("ts"), "channel": data.get("channel")}


def escalate_to_human(user_id: str, summary: str) -> Dict[str, Any]:
    return {"ok": True, "ticket_id": f"HUM-{user_id}", "summary": summary}


@traceable(
    name="CustomAgent", metadata={"agent": "CustomAgent", "tags": ["agent", "custom", "slack"]}
)
def custom_node(state: Dict[str, Any]) -> Dict[str, Any]:
    user_id = sget(state, "user_id", "unknown")
    message = sget(state, "message", "")
    meta = {"agent": "CustomAgent"}
    base_meta = sget_meta(state)
    try:
        conf = float((base_meta or {}).get("handoff_confidence") or 0.0)
    except Exception:
        conf = 0.0

    # Heurística simples: se mencionar "human" ou "help", aciona escalonamento
    if any(k in message.lower() for k in ["human", "help", "assist"]):
        res = escalate_to_human(user_id, summary=message)
        answer = "I've escalated your request to a human. We'll reach out shortly."
        grounding = {"mode": "slack/escalation", "tools": [res], "confidence": conf}
    else:
        channel = settings.slack_default_channel or "#support"
        res = send_slack_message(channel, f"{user_id}: {message}")
        answer = "I pinged our team on Slack. Meanwhile, is there anything else I can help with?"
        grounding = {"mode": "slack", "tools": [res], "confidence": conf}

    return {
        "answer": answer,
        "agent": "CustomAgent",
        "grounding": grounding,
        "meta": {**base_meta, **meta},
    }
