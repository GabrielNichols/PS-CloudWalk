from langgraph.graph import StateGraph, END
from app.graph.state import AppState
from app.agents.router import router_node, route_decision
from app.agents.knowledge import knowledge_node, knowledge_next
from app.agents.support import support_node
from app.agents.personality import personality_node
from app.agents.custom import custom_node


def build_graph(checkpointer=None):
    g = StateGraph(AppState)
    g.add_node("router", router_node)
    g.add_node("knowledge", knowledge_node)
    g.add_node("support", support_node)
    g.add_node("custom", custom_node)
    g.add_node("personality", personality_node)

    g.add_conditional_edges(
        "knowledge",
        knowledge_next,
        {
            "custom": "custom",
            "personality": "personality",
        },
    )
    g.add_edge("support", "personality")
    g.add_edge("custom", "personality")
    g.add_edge("personality", END)

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

    g.set_entry_point("router")
    return g.compile(checkpointer=checkpointer)
