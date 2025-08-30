from langgraph.graph import StateGraph, END, START, MessagesState, add_messages
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.store.base import BaseStore
from typing import Optional

from app.graph.state import AppState
from app.agents.router import intelligent_router_node, route_decision, router_node
from app.agents.knowledge.knowledge_node import knowledge_node, knowledge_next
from app.agents.support import support_node
from app.agents.personality import personality_node
from app.agents.custom import custom_node


def add_user_message(state):
    """
    Add user message to conversation history and preserve existing history.
    """
    # Get existing messages or start with empty list
    existing_messages = state.get("messages", [])

    # Add user message to conversation
    user_message = HumanMessage(content=state["message"])

    # Return updated state with new message appended
    return {"messages": existing_messages + [user_message]}


def add_ai_response(state):
    """
    Add AI response to conversation history.
    """
    if state.get("answer"):
        ai_message = AIMessage(content=state["answer"])
        return {"messages": [ai_message]}
    return {}


def retrieve_memory_node(state, config: RunnableConfig, *, store: BaseStore = None):
    """
    Node to retrieve relevant memories for the current conversation.
    Following LangGraph documentation pattern with semantic search.
    """
    if not store or not state.get("user_id"):
        return {}

    user_id = state["user_id"]
    current_message = state.get("message", "")

    # Get relevant memories using centralized function
    from app.graph.memory import search_user_memories
    memories = search_user_memories(user_id, current_message, "memories", limit=3)

    if memories:
        memory_texts = []
        for memory in memories:
            if isinstance(memory, dict) and "value" in memory:
                value = memory["value"]
                if isinstance(value, dict) and "data" in value:
                    memory_texts.append(str(value["data"]))

        if memory_texts:
            # Format memory context in a more structured way for better LLM understanding
            formatted_memories = []
            for i, text in enumerate(memory_texts, 1):
                formatted_memories.append(f"Conversation {i}: {text}")

            memory_context = f"""PREVIOUS CONVERSATIONS WITH THIS USER:
{' | '.join(formatted_memories)}

IMPORTANT: Use this information to personalize your response. If the user asks about their name or previous information, look in these conversations first."""

            return {"user_context": {"long_term_memory": memory_context}}

    return {"user_context": {"long_term_memory": ""}}


def store_memory_node(state, config: RunnableConfig, *, store: BaseStore = None):
    """
    Node to store new memories from the conversation.
    Following LangGraph documentation pattern.
    """
    if not store or not state.get("user_id"):
        return {}

    user_id = state["user_id"]
    user_message = state.get("message", "").strip()
    ai_response = state.get("answer", "").strip()

    # Only store if it's a meaningful message
    if len(user_message) > 5 and len(ai_response) > 5:
        # Store conversation memory using centralized function
        from app.graph.memory import store_conversation_memory
        store_conversation_memory(user_id, user_message, ai_response)

    return {}


def enhanced_personality_with_memory(state, config: RunnableConfig, *, store: BaseStore = None):
    """
    Enhanced personality agent with intelligent long-term memory.
    Uses centralized memory functions from memory.py.
    """
    from app.agents.personality import personality_node
    from app.graph.memory import get_user_memory_context

    # Get user memory context using centralized function
    user_id = state.get("user_id")
    current_message = state.get("message", "")

    memory_context = ""
    if user_id and current_message:
        memory_context = get_user_memory_context(user_id, current_message)

    # Add memory context to the state for personality agent
    enhanced_state = state.copy()
    if memory_context:
        enhanced_state["user_context"] = {
            "long_term_memory": memory_context,
            "memory_available": True
        }
        print("📋 Personality agent enhanced with long-term memory")

    # Process with personality agent
    result = personality_node(enhanced_state)

    # Store conversation using centralized function
    if user_id and result.get("answer"):
        from app.graph.memory import store_conversation_memory
        store_conversation_memory(user_id, current_message, result["answer"])

    return result


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


def build_graph(checkpointer=None, store=None):
    """
    Build the Agent Swarm graph with intelligent stateful routing and long-term memory.

    Features:
    - Stateful routing (continues conversation with same agent)
    - AI-powered intelligent routing decisions
    - Long-term memory for user-specific data across conversations
    - Memory-aware agent orchestration
    - Human-in-the-loop capabilities
    """
    # Use MessagesState for conversation memory + our custom state
    class CombinedState(MessagesState):
        # Core user input
        user_id: str
        message: str
        locale: str = None

        # Intelligent routing fields
        intent: str = None
        current_route: str = None  # Current active agent
        routing_history: list = []  # Track agent routing history
        routing_confidence: float = None
        routing_reason: str = None

        # Agent workflow data
        retrieval: dict = None
        answer: str = None
        agent: str = None
        grounding: dict = None

        # Memory and context
        user_context: dict = None
        conversation_context: dict = None

        # Metadata and tracing
        meta: dict = {}
        trace: dict = {}

        # Escalation and human-in-the-loop
        needs_human_escalation: bool = False
        escalation_reason: str = None
        human_response: str = None

    g = StateGraph(CombinedState)

    # Add message management nodes
    g.add_node("add_user_message", add_user_message)
    g.add_node("add_ai_response", add_ai_response)

    # Add memory nodes using centralized functions
    g.add_node("retrieve_memory", retrieve_memory_node)
    g.add_node("store_memory", store_memory_node)

    # Add all agent nodes
    g.add_node("intelligent_router", intelligent_router_node)  # AI-powered router
    g.add_node("router", router_node)  # Fallback keyword-based router
    g.add_node("knowledge", knowledge_node)
    g.add_node("support", support_node)
    g.add_node("custom", custom_node)
    g.add_node("personality", enhanced_personality_with_memory)  # Enhanced with memory

    # Start with adding user message to conversation history
    g.add_edge(START, "add_user_message")

    # Then retrieve relevant memories
    g.add_edge("add_user_message", "retrieve_memory")

    # Then route to appropriate agent
    g.add_conditional_edges(
        "retrieve_memory",
        pre_greeting_routing,
        {
            "intelligent_router": "intelligent_router",  # AI makes all routing decisions
            "knowledge": "knowledge",  # Continue with knowledge agent if needed
            "support": "support",      # Continue with support agent if needed
            "custom": "custom",        # Continue with custom agent if needed
            "personality": "personality",  # Direct to personality agent
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

    # Personality is the final step, then add AI response to history and store memory
    g.add_edge("personality", "add_ai_response")
    g.add_edge("add_ai_response", "store_memory")

    # Store memory is the final step
    g.add_edge("store_memory", END)

    return g.compile(checkpointer=checkpointer, store=store)