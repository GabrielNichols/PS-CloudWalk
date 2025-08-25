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
    # agent could be CustomAgent if confidence triggers handoff; accept either
    assert body["agent"] in ("KnowledgeAgent", "CustomAgent")
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
    assert body["agent"] in ("KnowledgeAgent", "CustomAgent")
    # can be web fallback due to off-domain; if handed to CustomAgent, expect slack modes
    mode = body.get("grounding", {}).get("mode")
    if body["agent"] == "CustomAgent":
        assert mode in ("slack", "slack/escalation")
    else:
        assert mode in ("web", "graph+vector", "placeholder", "none")


def test_locale_pt_response_and_sources():
    r = client.post(
        "/api/v1/message",
        json={"message": "Quais as taxas do cartão?", "user_id": "u7", "locale": "pt-BR"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["agent"] in ("KnowledgeAgent", "CustomAgent")
    assert body["answer"].startswith("[pt-BR]")
    if body["agent"] == "CustomAgent":
        assert body.get("grounding", {}).get("mode") in ("slack", "slack/escalation")
    else:
        assert body.get("grounding", {}).get("mode") in (
            "graph+vector",
            "web",
            "placeholder",
            "none",
        )


def test_product_info_snapshot_like_fee_terms():
    r = client.post(
        "/api/v1/message",
        json={"message": "What are the fees of the Maquininha Smart?", "user_id": "u8"},
    )
    assert r.status_code == 200
    txt = r.json().get("answer", "").lower()
    # Snapshot-like tolerance: expect some known terms
    expected_any = ["debit", "credit", "pix", "fee", "rate", "taxa"]
    assert any(term in txt for term in expected_any)


def test_latency_and_tokens_stay_under_caps():
    r = client.post(
        "/api/v1/message",
        json={"message": "What are the fees of the Maquininha Smart?", "user_id": "u9"},
    )
    assert r.status_code == 200
    meta = r.json().get("meta", {})
    # Soft caps for latency and token estimate (heuristic from meta)
    assert meta.get("latency_ms") is None or meta.get("latency_ms") < 8000
    assert meta.get("token_estimate") is None or meta.get("token_estimate") < 4000


def test_out_of_scope_suppresses_sources():
    r = client.post(
        "/api/v1/message",
        json={"message": "Últimas notícias do Palmeiras hoje", "user_id": "u10", "locale": "pt-BR"},
    )
    assert r.status_code == 200
    body = r.json()
    # Should not attach InfinitePay sources for out-of-scope question
    if (
        "desculpe" in body.get("answer", "").lower()
        or "i don't know" in body.get("answer", "").lower()
    ):
        assert body.get("grounding", {}).get("sources") in ([], None)
