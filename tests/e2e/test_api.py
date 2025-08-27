from fastapi.testclient import TestClient
from app.api.main import app


client = TestClient(app)


def test_message_knowledge_stub():
    r = client.post(
        "/api/v1/message",
        json={"message": "What are the fees of the Maquininha Smart?", "user_id": "u1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["agent"] in {"KnowledgeAgent", "CustomerSupportAgent", "CustomAgent"}
    assert isinstance(body.get("answer"), str)


def test_message_support_stub():
    r = client.post(
        "/api/v1/message",
        json={"message": "I can't sign in to my account.", "user_id": "u2"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["agent"] == "CustomerSupportAgent"
    assert "Ticket" in body["answer"]
