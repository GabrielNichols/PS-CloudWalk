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


# No hardcoded hints or keywords - let AI decide everything intelligently


def _detect_intent(message: str) -> str:
    """Simple fallback intent detection - AI should handle most decisions."""
    # This is only used as fallback when AI routing fails
    # Let the AI make intelligent decisions instead of hardcoded rules
    return "knowledge"  # Default fallback when AI is unavailable


@traceable(name="RouterAgent", metadata={"agent": "RouterAgent", "tags": ["agent", "router"]})
def router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    state = enforce(state)
    message = (state.get("message") if isinstance(state, dict) else None) or ""
    user_id = state.get("user_id") if isinstance(state, dict) else None
    locale = state.get("locale") if isinstance(state, dict) else None

    # Let the AI detect language naturally from context
    # No hardcoded language detection

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


# Completely free AI routing - no hardcoded tools or agents
# AI decides everything autonomously based on context and message content

def _get_routing_llm_client() -> Optional[OpenAI]:
    """Get LLM client for intelligent routing."""
    if not settings.openai_api_key:
        return None
    return OpenAI(api_key=settings.openai_api_key)

def _intelligent_routing(message: str, user_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Completely free AI routing - no hardcoded tools or constraints."""
    client = _get_routing_llm_client()
    if not client:
        # Simple fallback when AI is unavailable
        return {
            "intent": "knowledge",
            "target_agent": "knowledge",
            "routing_confidence": 0.5,
            "routing_reason": "AI unavailable - using default routing",
            "fallback": True
        }

    # Get user context for better routing decisions
    context_prompt = get_user_context_prompt(user_id) if user_id else ""

    # Use structured routing prompt
    from app.agents.prompts import build_system_prompt, create_agent_messages

    # Create structured messages
    messages = create_agent_messages(
        agent_name="router",
        user_message=message,
        user_context=context_prompt
    )

    try:
        # Convert to OpenAI format for API call
        openai_messages = []
        for msg in messages:
            if hasattr(msg, 'type'):
                if msg.type == 'system':
                    openai_messages.append({"role": "system", "content": msg.content})
                elif msg.type == 'human':
                    openai_messages.append({"role": "user", "content": msg.content})

        response = client.chat.completions.create(
            model=settings.openai_model or "gpt-4o-mini",
            messages=openai_messages,
            temperature=0.3,  # Slight creativity for better decisions
            max_tokens=100
        )

        ai_decision = response.choices[0].message.content.strip()

        # Parse AI decision
        agent_mapping = {
            "personality": "personality",
            "personalityagent": "personality",
            "knowledge": "knowledge",
            "knowledgeagent": "knowledge",
            "support": "support",
            "customersupportagent": "support",
            "custom": "custom",
            "customagent": "custom"
        }

        # Extract agent from AI response
        ai_lower = ai_decision.lower()
        target_agent = "knowledge"  # Default

        for key, agent in agent_mapping.items():
            if key in ai_lower:
                target_agent = agent
                break

        return {
            "intent": target_agent,
            "target_agent": target_agent,
            "routing_confidence": 0.9,
            "routing_reason": f"AI decided: {ai_decision}",
            "fallback": False
        }

    except Exception as e:
        print(f"⚠️ AI routing failed: {e}, using fallback")
        return {
            "intent": "knowledge",
            "target_agent": "knowledge",
            "routing_confidence": 0.5,
            "routing_reason": "AI routing failed - using fallback",
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
