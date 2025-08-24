from typing import Dict, Any
from app.graph.helpers import sget, sget_meta

from langsmith import traceable


def send_slack_message(channel: str, text: str) -> Dict[str, Any]:
    # Stubbed tool; in real usage integrate Slack Web API
    return {"ok": True, "channel": channel, "text": text}


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

    # Heurística simples: se mencionar "human" ou "help", aciona escalonamento
    if any(k in message.lower() for k in ["human", "help", "assist"]):
        res = escalate_to_human(user_id, summary=message)
        answer = "I've escalated your request to a human. We'll reach out shortly."
        grounding = {"mode": "slack/escalation", "tools": [res]}
    else:
        res = send_slack_message("#support", f"{user_id}: {message}")
        answer = "I pinged our team on Slack. Meanwhile, is there anything else I can help with?"
        grounding = {"mode": "slack", "tools": [res]}

    return {
        "answer": answer,
        "agent": "CustomAgent",
        "grounding": grounding,
        "meta": {**base_meta, **meta},
    }
