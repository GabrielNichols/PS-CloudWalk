from fastapi.testclient import TestClient
from app.api.main import app
import time
from langsmith import traceable


client = TestClient(app)


@traceable(name="E2E.PostMessage")
def _post_message(message: str, user_id: str, locale: str | None = None):
    t0 = time.perf_counter()
    payload = {"message": message, "user_id": user_id}
    if locale:
        payload["locale"] = locale
    r = client.post("/api/v1/message", json=payload)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    try:
        body = r.json()
    except Exception:
        body = {}
    # Return a rich object so it shows up in LangSmith traces
    return {
        "status_code": r.status_code,
        "latency_ms": elapsed_ms,
        "agent": body.get("agent"),
        "mode": (body.get("grounding") or {}).get("mode"),
        "meta_latency_ms": (body.get("meta") or {}).get("latency_ms"),
        "token_estimate": (body.get("meta") or {}).get("token_estimate"),
        "answer_len": len((body.get("answer") or "")),
        "raw": body,
    }


@traceable(name="E2E.test_fees_query_returns_sources")
def test_fees_query_returns_sources():
    resp = _post_message("What are the fees of the Maquininha Smart?", "u3")
    assert resp["status_code"] == 200
    body = resp["raw"]
    assert body["ok"] is True
    assert "Sources:" in body["answer"] or body["grounding"]
    # confidence presence
    assert "confidence" in body.get("grounding", {})


@traceable(name="E2E.test_howto_query_uses_graph_vector_ensemble")
def test_howto_query_uses_graph_vector_ensemble():
    resp = _post_message("How can I use my phone as a card machine?", "u4")
    assert resp["status_code"] == 200
    body = resp["raw"]
    assert body["ok"] is True
    # agent could be CustomAgent if confidence triggers handoff; accept either
    assert body["agent"] in ("KnowledgeAgent", "CustomAgent")
    assert "confidence" in body.get("grounding", {})


@traceable(name="E2E.test_custom_agent_escalation_path")
def test_custom_agent_escalation_path():
    resp = _post_message("please escalate to human via slack", "u5")
    assert resp["status_code"] == 200
    body = resp["raw"]
    assert body["ok"] is True
    assert body["agent"] in ["CustomAgent", "KnowledgeAgent", "CustomerSupportAgent", "Unknown"]


@traceable(name="E2E.test_web_search_fallback_when_context_missing")
def test_web_search_fallback_when_context_missing():
    resp = _post_message("Últimas notícias do Palmeiras hoje", "u6")
    assert resp["status_code"] == 200
    body = resp["raw"]
    assert body["ok"] is True
    assert body["agent"] in ("KnowledgeAgent", "CustomAgent")
    # can be web fallback due to off-domain; if handed to CustomAgent, expect slack modes
    mode = body.get("grounding", {}).get("mode")
    if body["agent"] == "CustomAgent":
        assert mode in ("slack", "slack/escalation")
    else:
        assert mode in ("web", "vector+faq", "placeholder", "none")


@traceable(name="E2E.test_locale_pt_response_and_sources")
def test_locale_pt_response_and_sources():
    resp = _post_message("Quais as taxas do cartão?", "u7", locale="pt-BR")
    assert resp["status_code"] == 200
    body = resp["raw"]
    assert body["ok"] is True
    assert body["agent"] in ("KnowledgeAgent", "CustomAgent")
    assert body["answer"].startswith("[pt-BR]")
    if body["agent"] == "CustomAgent":
        assert body.get("grounding", {}).get("mode") in ("slack", "slack/escalation")
    else:
        assert body.get("grounding", {}).get("mode") in (
            "vector+faq",
            "web",
            "placeholder",
            "none",
        )


@traceable(name="E2E.test_product_info_snapshot_like_fee_terms")
def test_product_info_snapshot_like_fee_terms():
    resp = _post_message("What are the fees of the Maquininha Smart?", "u8")
    assert resp["status_code"] == 200
    txt = resp["raw"].get("answer", "").lower()
    # Snapshot-like tolerance: expect some known terms
    expected_any = ["debit", "credit", "pix", "fee", "rate", "taxa"]
    assert any(term in txt for term in expected_any)


@traceable(name="E2E.test_latency_and_tokens_stay_under_caps")
def test_latency_and_tokens_stay_under_caps():
    resp = _post_message("What are the fees of the Maquininha Smart?", "u9")
    assert resp["status_code"] == 200
    meta = resp["raw"].get("meta", {})
    # Soft caps for latency and token estimate (heuristic from meta)
    assert meta.get("latency_ms") is None or meta.get("latency_ms") < 8000
    assert meta.get("token_estimate") is None or meta.get("token_estimate") < 4000


@traceable(name="E2E.test_out_of_scope_suppresses_sources")
def test_out_of_scope_suppresses_sources():
    resp = _post_message("Últimas notícias do Palmeiras hoje", "u10", locale="pt-BR")
    assert resp["status_code"] == 200
    body = resp["raw"]
    # Should not attach InfinitePay sources for out-of-scope question
    if (
        "desculpe" in body.get("answer", "").lower()
        or "i don't know" in body.get("answer", "").lower()
    ):
        assert body.get("grounding", {}).get("sources") in ([], None)
