from typing import Dict, Any
from app.tools.user_profile import get_user_info
from app.tools.ticketing import open_ticket

from langsmith import traceable


@traceable(
    name="CustomerSupportAgent",
    metadata={"agent": "CustomerSupportAgent", "tags": ["agent", "support"]},
)
def support_node(state: Dict[str, Any]) -> Dict[str, Any]:
    user_id = (state.get("user_id") if isinstance(state, dict) else None) or "unknown"
    profile = get_user_info(user_id)
    # Simple heuristic: if message mentions transfer/login, propose human help
    message = ((state.get("message") if isinstance(state, dict) else None) or "").lower()
    category = (
        "transfer" if "transfer" in message else "login" if "sign in" in message or "login" in message else "general"
    )
    message = (state.get("message") if isinstance(state, dict) else None) or ""
    ticket = open_ticket(user_id, category, summary=str(message))
    answer = (
        "CustomerSupportAgent: I opened a support ticket and summarized your issue. "
        f"Ticket {ticket['id']} is now open. Our team will contact you shortly."
    )
    grounding = {
        "mode": "tools",
        "sources": [
            {"type": "user_profile", "data": profile},
            {"type": "ticket", "data": ticket},
        ],
    }
    meta = {"agent": "CustomerSupportAgent"}
    base_meta: dict = {}
    return {
        "answer": answer,
        "agent": "CustomerSupportAgent",
        "grounding": grounding,
        "meta": {**base_meta, **meta},
    }
