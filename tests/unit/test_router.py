from app.agents.router import router_node, route_decision


def test_router_sets_intent_knowledge():
    state = {"message": "What are the fees?", "user_id": "u"}
    out = router_node(state)
    assert out["intent"] == "knowledge"
    assert route_decision(out) == "knowledge"


def test_router_sets_intent_support():
    state = {"message": "I can't sign in to my account", "user_id": "u"}
    out = router_node(state)
    assert out["intent"] == "support"
    assert route_decision(out) == "support"
