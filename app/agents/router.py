from typing import Dict, Any, Optional
import json
from datetime import datetime

from langsmith import traceable
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from langdetect import detect
from app.graph.guardrails import enforce
from app.graph.memory import get_user_context_prompt, update_user_context
from app.settings import settings
from openai import OpenAI


# Greeting keywords - should not trigger complex processing
GREETING_HINTS = [
    "ola", "olá", "oi", "hi", "hello", "hey", "bom dia", "boa tarde",
    "boa noite", "good morning", "good afternoon", "good evening",
    "greetings", "saudações", "cumprimentos"
]

KNOWLEDGE_HINTS = [
    "fee", "cost", "rate", "maquininha", "tap to pay", "pix", "pdv",
    "link de pagamento", "conta", "cartão", "boleto", "emprestimo", "rendimento",
    "como funciona", "how does", "what is", "quanto custa", "how much",
    "preço", "price", "taxa", "rate", "tarifa"
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
    "support",
    "connect",
    "talk to",
    "speak to",
    "attendant",
    "atendente",
    "person",
    "pessoa",
    "representative",
    "representante",
]


def _detect_intent(message: str) -> str:
    """Enhanced intent detection with greeting, custom, support, and knowledge routing."""
    lower = message.lower().strip()

    # Check for simple greetings first (highest priority)
    for hint in GREETING_HINTS:
        if hint in lower:
            print(f"🔄 Router: Detected GREETING for '{message}' (matched: '{hint}')")
            return "greeting"

    # Check CUSTOM hints (human escalation)
    for hint in CUSTOM_HINTS:
        if hint in lower:
            print(f"🔄 Router: Detected CUSTOM intent for '{message}' (matched: '{hint}')")
            return "custom"

    # Check SUPPORT hints (account/technical issues)
    for hint in SUPPORT_HINTS:
        if hint in lower:
            print(f"🔄 Router: Detected SUPPORT intent for '{message}' (matched: '{hint}')")
            return "support"

    # Check KNOWLEDGE hints (product questions)
    for hint in KNOWLEDGE_HINTS:
        if hint in lower:
            print(f"🔄 Router: Detected KNOWLEDGE intent for '{message}' (matched: '{hint}')")
            return "knowledge"

    # Default fallback - for ambiguous messages, assume greeting
    print(f"🔄 Router: No specific keywords matched for '{message}', treating as greeting")
    return "greeting"


@traceable(name="RouterAgent", metadata={"agent": "RouterAgent", "tags": ["agent", "router"]})
def router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    state = enforce(state)
    message = (state.get("message") if isinstance(state, dict) else None) or ""
    user_id = state.get("user_id") if isinstance(state, dict) else None
    locale = state.get("locale") if isinstance(state, dict) else None

    if not locale and message:
        try:
            lang = detect(message)
            locale = "pt-BR" if lang.startswith("pt") else "en"
        except Exception:  # noqa: BLE001
            locale = "en"

    intent = _detect_intent(message)

    # Log routing decision for debugging
    print(f"🎯 Router: User {user_id} -> {intent.upper()} (message: '{message[:50]}...')")

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


# AI-Powered Routing Tools
@tool(parse_docstring=True, response_format="content_and_artifact")
def route_to_greeting_response(reason: str) -> tuple:
    """Route simple greetings to a quick personality response without complex processing.

    Args:
        reason: Explanation of why this simple greeting routing was chosen
    """
    return f"Simple greeting response: {reason}", {
        "target_agent": "personality",
        "routing_reason": reason,
        "routing_confidence": 0.95,
        "simple_greeting": True,
        "timestamp": datetime.now().isoformat()
    }

@tool(parse_docstring=True, response_format="content_and_artifact")
def route_to_knowledge_agent(reason: str) -> tuple:
    """Route the user to the Knowledge Agent for product information and RAG queries.

    Args:
        reason: Explanation of why this routing decision was made
    """
    return f"Routing to Knowledge Agent: {reason}", {
        "target_agent": "knowledge",
        "routing_reason": reason,
        "routing_confidence": 0.9,
        "timestamp": datetime.now().isoformat()
    }

@tool(parse_docstring=True, response_format="content_and_artifact")
def route_to_support_agent(reason: str) -> tuple:
    """Route the user to the Customer Support Agent for account and technical issues.

    Args:
        reason: Explanation of why this routing decision was made
    """
    return f"Routing to Support Agent: {reason}", {
        "target_agent": "support",
        "routing_reason": reason,
        "routing_confidence": 0.9,
        "timestamp": datetime.now().isoformat()
    }

@tool(parse_docstring=True, response_format="content_and_artifact")
def route_to_custom_agent(reason: str) -> tuple:
    """Route the user to the Custom Agent for escalations and human assistance.

    Args:
        reason: Explanation of why this routing decision was made
    """
    return f"Routing to Custom Agent: {reason}", {
        "target_agent": "custom",
        "routing_reason": reason,
        "routing_confidence": 0.9,
        "timestamp": datetime.now().isoformat()
    }

def _get_routing_llm_client() -> Optional[OpenAI]:
    """Get LLM client for intelligent routing."""
    if not settings.openai_api_key:
        return None
    return OpenAI(api_key=settings.openai_api_key)

def _intelligent_routing(message: str, user_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Use AI to make intelligent routing decisions based on user context and message."""
    client = _get_routing_llm_client()
    if not client:
        # Fallback to keyword-based routing
        intent = _detect_intent(message)
        return {
            "intent": intent,
            "target_agent": intent,
            "routing_confidence": 0.7,
            "routing_reason": "Keyword-based routing (LLM unavailable)",
            "fallback": True
        }

    # Get user context for better routing decisions
    context_prompt = get_user_context_prompt(user_id) if user_id else ""

    routing_prompt = f"""You are an intelligent router for an InfinitePay customer support system.

User Context: {context_prompt}

User Message: "{message}"

Available Routing Options:
1. **Greeting Response**: For simple greetings like "hello", "hi", "ola", "bom dia" - respond with a simple welcome
2. **Knowledge Agent**: For questions about InfinitePay products, fees, features, and general information from the website
3. **Support Agent**: For account issues, login problems, transfers, technical support, and customer service requests
4. **Custom Agent**: For escalations to humans, complex issues, and requests for direct human assistance

Routing Guidelines:
- Simple greetings (ola, hello, hi, bom dia) → Greeting Response
- Product questions (fees, features, how it works) → Knowledge Agent
- Account problems (login, transfers, errors) → Support Agent
- Human requests (speak to person, connect to support) → Custom Agent

Consider:
- User's previous interactions and preferences
- The nature of their current request
- Whether they need product information, technical help, or human escalation
- Language preferences and communication style

Choose the most appropriate routing option based on the user's message and context.
"""

    try:
        response = client.chat.completions.create(
            model=settings.openai_model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": routing_prompt},
                {"role": "user", "content": message}
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "route_to_greeting_response",
                        "description": "Route simple greetings to quick personality response",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "reason": {"type": "string", "description": "Why this simple greeting routing was chosen"}
                            },
                            "required": ["reason"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "route_to_knowledge_agent",
                        "description": "Route to Knowledge Agent for product information",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "reason": {"type": "string", "description": "Why this routing was chosen"}
                            },
                            "required": ["reason"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "route_to_support_agent",
                        "description": "Route to Support Agent for account/technical issues",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "reason": {"type": "string", "description": "Why this routing was chosen"}
                            },
                            "required": ["reason"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "route_to_custom_agent",
                        "description": "Route to Custom Agent for human escalation",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "reason": {"type": "string", "description": "Why this routing was chosen"}
                            },
                            "required": ["reason"]
                        }
                    }
                }
            ],
            temperature=0.0
        )

        # Parse the tool call response
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            agent_mapping = {
                "route_to_greeting_response": "personality",  # Simple greeting response
                "route_to_knowledge_agent": "knowledge",
                "route_to_support_agent": "support",
                "route_to_custom_agent": "custom"
            }

            target_agent = agent_mapping.get(tool_name, "personality")  # Default to personality for greetings
            routing_reason = tool_args.get("reason", "AI-powered routing decision")

            # Set flag for simple greetings to optimize processing
            is_simple_greeting = tool_name == "route_to_greeting_response"

            return {
                "intent": target_agent,
                "target_agent": target_agent,
                "routing_confidence": 0.95,
                "routing_reason": routing_reason,
                "fallback": False,
                "simple_greeting": is_simple_greeting
            }

    except Exception as e:
        print(f"⚠️ AI routing failed: {e}, using keyword fallback")

    # Fallback to keyword-based routing
    intent = _detect_intent(message)
    return {
        "intent": intent,
        "target_agent": intent,
        "routing_confidence": 0.7,
        "routing_reason": "Keyword-based routing (AI routing failed)",
        "fallback": True
    }

@traceable(name="IntelligentRouter", metadata={"agent": "RouterAgent", "tags": ["router", "ai-routing"]})
def intelligent_router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Intelligent router that uses AI to make routing decisions."""
    state = enforce(state)
    message = state.get("message", "")
    user_id = state.get("user_id", "unknown")

    # Get user context for intelligent routing
    try:
        user_context = get_user_context_prompt(user_id)
    except Exception:
        user_context = ""

    # Use AI-powered routing
    routing_decision = _intelligent_routing(message, user_id, state)

    # Update routing history
    routing_history = state.get("routing_history", [])
    routing_history.append({
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "decision": routing_decision["target_agent"],
        "confidence": routing_decision["routing_confidence"],
        "reason": routing_decision["routing_reason"],
        "fallback": routing_decision["fallback"]
    })

    # Log routing decision
    print(f"🎯 AI Router: {user_id} -> {routing_decision['target_agent'].upper()}")
    print(f"   Confidence: {routing_decision['routing_confidence']}")
    print(f"   Reason: {routing_decision['routing_reason']}")
    if routing_decision["fallback"]:
        print("   📝 Using keyword fallback")

    # Return enhanced state
    return {
        "intent": routing_decision["intent"],
        "current_route": routing_decision["target_agent"],
        "routing_history": routing_history,
        "routing_confidence": routing_decision["routing_confidence"],
        "routing_reason": routing_decision["routing_reason"],
        "user_context": user_context,
        "message": message,
        "user_id": user_id
    }

@traceable(name="RouterDecision", metadata={"agent": "RouterAgent", "tags": ["router", "decision"]})
def route_decision(state: Dict[str, Any]) -> str:
    """Enhanced routing decision with memory awareness."""
    current_route = state.get("current_route")
    routing_history = state.get("routing_history", [])

    # If we have an active route and recent history, continue with it
    if current_route and routing_history:
        last_routing = routing_history[-1] if routing_history else {}
        if last_routing.get("confidence", 0) > 0.8:
            print(f"🔄 Continuing with active route: {current_route}")
            return current_route

    # New routing decision
    intent = state.get("intent")
    if intent == "custom":
        return "custom"
    if intent == "support":
        return "support"
    if intent == "knowledge":
        return "knowledge"

    return "knowledge"  # Default fallback
