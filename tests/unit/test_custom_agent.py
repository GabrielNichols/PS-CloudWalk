from app.agents.custom import custom_node


def test_custom_agent_escalates_when_asked_for_human():
    out = custom_node({"user_id": "u1", "message": "Please escalate to human"})
    assert out["agent"] == "CustomAgent"
    assert out["grounding"]["mode"].startswith("slack")


def test_custom_agent_posts_slack_by_default():
    out = custom_node({"user_id": "u1", "message": "ping team"})
    assert out["agent"] == "CustomAgent"
    assert out["grounding"]["mode"] == "slack"
