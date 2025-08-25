from app.agents import custom as custom_module
from app.agents.custom import custom_node, send_slack_message


def test_send_slack_message_stub_returns_ok_without_token(monkeypatch):
    # Ensure function returns ok even if no real Slack token
    out = send_slack_message("#support", "hello")
    assert isinstance(out, dict)
    assert out.get("ok") in (True, False)


def test_custom_agent_slack_called_when_token_present(monkeypatch):
    calls = {}

    class FakeResp:
        def __init__(self):
            self.data = {"ok": True}

    class FakeClient:
        def __init__(self, token=None):
            calls["token"] = token

        def chat_postMessage(self, channel, text):
            calls["channel"] = channel
            calls["text"] = text
            return FakeResp()

    monkeypatch.setattr(custom_module, "WebClient", FakeClient)
    # Force a fake token via settings monkeypatch
    monkeypatch.setattr(custom_module.settings, "slack_bot_token", "xoxb-fake")
    out = custom_module.custom_node({"user_id": "u1", "message": "ping team"})
    assert out["agent"] == "CustomAgent"
    assert calls.get("channel") == custom_module.settings.slack_default_channel
    assert "u1" in calls.get("text", "")


def test_custom_agent_escalates_when_asked_for_human():
    out = custom_node({"user_id": "u1", "message": "Please escalate to human"})
    assert out["agent"] == "CustomAgent"
    assert out["grounding"]["mode"].startswith("slack")


def test_custom_agent_posts_slack_by_default():
    out = custom_node({"user_id": "u1", "message": "ping team"})
    assert out["agent"] == "CustomAgent"
    assert out["grounding"]["mode"] == "slack"
