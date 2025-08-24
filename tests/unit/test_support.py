from app.agents.support import support_node


def test_support_opens_ticket():
    state = {"user_id": "u1", "message": "I can't sign in to my account"}
    out = support_node(state)
    assert out["agent"] == "CustomerSupportAgent"
    assert "Ticket" in out["answer"]
    assert out["grounding"]["mode"] == "tools"
