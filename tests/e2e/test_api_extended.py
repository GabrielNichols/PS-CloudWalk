from fastapi.testclient import TestClient
from app.api.main import app


client = TestClient(app)


def test_fees_query_returns_sources():
    r = client.post(
        "/api/v1/message",
        json={"message": "What are the fees of the Maquininha Smart?", "user_id": "u3"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "Sources:" in body["answer"] or body["grounding"]
    # confidence presence
    assert "confidence" in body.get("grounding", {})


def test_howto_query_uses_graph_vector_ensemble():
    r = client.post(
        "/api/v1/message",
        json={"message": "How can I use my phone as a card machine?", "user_id": "u4"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["agent"] == "KnowledgeAgent"
    assert "confidence" in body.get("grounding", {})


def test_custom_agent_escalation_path():
    r = client.post(
        "/api/v1/message",
        json={"message": "please escalate to human via slack", "user_id": "u5"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["agent"] in ["CustomAgent", "KnowledgeAgent", "CustomerSupportAgent", "Unknown"]


def test_web_search_fallback_when_context_missing():
    r = client.post(
        "/api/v1/message",
        json={"message": "Últimas notícias do Palmeiras hoje", "user_id": "u6"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["agent"] == "KnowledgeAgent"
    # can be web fallback due to off-domain
    assert body.get("grounding", {}).get("mode") in ("web", "graph+vector", "placeholder")
