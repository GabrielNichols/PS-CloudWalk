from typing import Dict, Any

from langsmith import traceable


from langdetect import detect
from app.graph.guardrails import enforce


KNOWLEDGE_HINTS = [
    "fee",
    "cost",
    "rate",
    "maquininha",
    "tap to pay",
    "pix",
    "pdv",
    "link de pagamento",
    "conta",
]
SUPPORT_HINTS = [
    "not able to",
    "can't",
    "nao consigo",
    "não consigo",
    "erro",
    "reset",
    "sign in",
    "transfer",
]
CUSTOM_HINTS = [
    "human",
    "escalate",
    "slack",
    "help",
]


def _detect_intent(message: str) -> str:
    lower = message.lower()
    if any(h in lower for h in CUSTOM_HINTS):
        return "custom"
    if any(h in lower for h in SUPPORT_HINTS):
        return "support"
    if any(h in lower for h in KNOWLEDGE_HINTS):
        return "knowledge"
    return "knowledge"  # default to knowledge


@traceable(name="RouterAgent", metadata={"agent": "RouterAgent", "tags": ["agent", "router"]})
def router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    state = enforce(state)
    message = (state.get("message") if isinstance(state, dict) else None) or ""
    locale = state.get("locale") if isinstance(state, dict) else None
    if not locale and message:
        try:
            lang = detect(message)
            locale = "pt-BR" if lang.startswith("pt") else "en"
        except Exception:  # noqa: BLE001
            locale = "en"
    intent = _detect_intent(message)

    # Preserve original state fields and add routing results
    result = {
        "intent": intent,
        "locale": locale
    }

    # Preserve original fields from input state
    for key in ["user_id", "message"]:
        if key in state:
            result[key] = state[key]

    return result


@traceable(name="RouterDecision", metadata={"agent": "RouterAgent", "tags": ["router", "decision"]})
def route_decision(state: Dict[str, Any]) -> str:
    intent = state.get("intent") if isinstance(state, dict) else None
    if intent == "custom":
        return "custom"
    if intent == "support":
        return "support"
    if intent == "knowledge":
        return "knowledge"
    return "end"
