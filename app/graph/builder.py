from langgraph.graph import StateGraph, END, START
from app.graph.state import AppState
from app.agents.router import intelligent_router_node, route_decision, router_node
from app.agents.knowledge.knowledge_node import knowledge_node, knowledge_next
from app.agents.support import support_node
from app.agents.personality import personality_node
from app.agents.custom import custom_node


def pre_greeting_routing(state):
    """
    Intelligent stateful routing that lets AI decide everything.

    No hardcoded rules - AI analyzes context and makes smart decisions.
    """
    current_route = state.get("current_route")
    routing_history = state.get("routing_history", [])

    # Check if we should continue with existing agent based on context
    if current_route and routing_history:
        last_routing = routing_history[-1] if routing_history else {}
        confidence = last_routing.get("confidence", 0)

        # Continue with active route if confidence is high and context suggests continuation
        if confidence > 0.8:
            print(f"🔄 Stateful routing: Continuing with {current_route} (confidence: {confidence})")
            return current_route

    # Let AI make intelligent routing decisions for all cases
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

    # Intelligent routing - AI decides everything based on context
    g.add_conditional_edges(
        START,
        pre_greeting_routing,
        {
            "intelligent_router": "intelligent_router",  # AI makes all routing decisions
            "knowledge": "knowledge",  # Continue with knowledge agent if needed
            "support": "support",      # Continue with support agent if needed
            "custom": "custom",        # Continue with custom agent if needed
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
            "personality": "personality",  # AI can route to personality for greetings
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
