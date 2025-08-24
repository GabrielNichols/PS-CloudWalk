from typing import Dict, Any
from app.graph.helpers import sget, sget_meta
from app.tools.user_profile import get_user_info
from app.tools.ticketing import open_ticket

from langsmith import traceable


@traceable(
    name="CustomerSupportAgent",
    metadata={"agent": "CustomerSupportAgent", "tags": ["agent", "support"]},
)
def support_node(state: Dict[str, Any]) -> Dict[str, Any]:
    user_id = sget(state, "user_id", "unknown")
    profile = get_user_info(user_id)
    # Simple heuristic: if message mentions transfer/login, propose human help
    message = sget(state, "message", "").lower()
    category = (
        "transfer"
        if "transfer" in message
        else "login" if "sign in" in message or "login" in message else "general"
    )
    ticket = open_ticket(user_id, category, summary=sget(state, "message", ""))
    answer = (
        "CustomerSupportAgent: I opened a support ticket and summarized your issue. "
        f"Ticket {ticket['id']} is now open. Our team will contact you shortly."
        "\nIf you need product information while you wait, you can check InfinitePay help pages."
        "\nSources: https://www.infinitepay.io/"
    )
    grounding = {
        "mode": "tools",
        "sources": [
            {"type": "user_profile", "data": profile},
            {"type": "ticket", "data": ticket},
        ],
    }
    meta = {"agent": "CustomerSupportAgent"}
    base_meta = sget_meta(state)
    return {
        "answer": answer,
        "agent": "CustomerSupportAgent",
        "grounding": grounding,
        "meta": {**base_meta, **meta},
    }
