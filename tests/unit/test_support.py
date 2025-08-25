from app.agents import support as support_module
from app.agents.support import support_node


def test_support_opens_ticket():
    state = {"user_id": "u1", "message": "I can't sign in to my account"}
    out = support_node(state)
    assert out["agent"] == "CustomerSupportAgent"
    assert "Ticket" in out["answer"]
    assert out["grounding"]["mode"] == "tools"


def test_support_returns_help_links():
    out = support_node({"user_id": "u2", "message": "I can't sign in"})
    assert out["agent"] == "CustomerSupportAgent"
    # After change, agent should NOT include sources/links for ticket confirmation
    assert "http" not in out["answer"].lower()


def test_support_tools_invoked(monkeypatch):
    captured = {}

    def fake_get_user_info(user_id: str):
        captured["profile_called_with"] = user_id
        return {"user_id": user_id, "status": "mock"}

    def fake_open_ticket(user_id: str, category: str, summary: str):
        captured["ticket_called_with"] = (user_id, category)
        return {"id": "T-00001", "user_id": user_id, "category": category, "status": "open"}

    monkeypatch.setattr(support_module, "get_user_info", fake_get_user_info)
    monkeypatch.setattr(support_module, "open_ticket", fake_open_ticket)

    out = support_node({"user_id": "u99", "message": "I can't sign in"})
    assert captured["profile_called_with"] == "u99"
    assert captured["ticket_called_with"][0] == "u99"
    assert out["grounding"]["mode"] == "tools"
