from langgraph.graph import StateGraph, END, START
from app.graph.state import AppState
from app.agents.router import intelligent_router_node, route_decision, router_node
from app.agents.knowledge.knowledge_node import knowledge_node, knowledge_next
from app.agents.support import support_node
from app.agents.personality import personality_node
from app.agents.custom import custom_node


def pre_greeting_routing(state):
    """
    Stateful routing: Route to the last used agent if available.

    Enhanced with greeting optimization for better UX.
    """
    current_route = state.get("current_route")
    routing_history = state.get("routing_history", [])
    message = state.get("message", "").lower().strip()

    # Check if this is a simple greeting - skip complex routing
    greeting_keywords = ["ola", "olá", "oi", "hi", "hello", "hey", "bom dia", "boa tarde", "boa noite"]
    if any(word in message for word in greeting_keywords) and len(message.split()) <= 3:
        print("🔄 Quick greeting detected, routing to personality for fast response")
        return "personality"

    # If we have an active route and recent history, continue with it
    if current_route and routing_history:
        last_routing = routing_history[-1] if routing_history else {}
        confidence = last_routing.get("confidence", 0)

        # Continue with active route if confidence is high
        if confidence > 0.8:
            print(f"🔄 Stateful routing: Continuing with {current_route} (confidence: {confidence})")
            return current_route

    # Default to intelligent router for new conversations
    return "intelligent_router"


def post_routing_decision(state):
    """
    Decide what to do after routing: go to agent or end.
    """
    current_route = state.get("current_route")
    if current_route and current_route != "end":
        return current_route
    return END


def build_graph(checkpointer=None):
    """
    Build the Agent Swarm graph with intelligent stateful routing.

    Features:
    - Stateful routing (continues conversation with same agent)
    - AI-powered intelligent routing decisions
    - Memory-aware agent orchestration
    - Human-in-the-loop capabilities
    """
    # Use dict instead of AppState to avoid Pydantic issues in LangGraph
    g = StateGraph(dict)

    # Add all agent nodes
    g.add_node("intelligent_router", intelligent_router_node)  # AI-powered router
    g.add_node("router", router_node)  # Fallback keyword-based router
    g.add_node("knowledge", knowledge_node)
    g.add_node("support", support_node)
    g.add_node("custom", custom_node)
    g.add_node("personality", personality_node)

    # Pre-routing: Check if we should continue with existing agent
    g.add_conditional_edges(
        START,
        pre_greeting_routing,
        {
            "intelligent_router": "intelligent_router",  # New conversation - use AI routing
            "knowledge": "knowledge",  # Continue with knowledge agent
            "support": "support",      # Continue with support agent
            "custom": "custom",        # Continue with custom agent
        }
    )

    # Intelligent router distributes to appropriate agents
    g.add_conditional_edges(
        "intelligent_router",
        post_routing_decision,
        {
            "knowledge": "knowledge",
            "support": "support",
            "custom": "custom",
            END: END,
        }
    )

    # Fallback router (keyword-based) - used when AI routing fails
    g.add_conditional_edges(
        "router",
        route_decision,
        {
            "knowledge": "knowledge",
            "support": "support",
            "custom": "custom",
            "end": END,
        },
    )

    # Knowledge agent can escalate or continue to personality
    g.add_conditional_edges(
        "knowledge",
        knowledge_next,
        {
            "custom": "custom",      # Escalate to human
            "personality": "personality",  # Normal flow
        },
    )

    # Support and Custom agents always go to personality
    g.add_edge("support", "personality")
    g.add_edge("custom", "personality")

    # Personality is the final step
    g.add_edge("personality", END)

    return g.compile(checkpointer=checkpointer)
