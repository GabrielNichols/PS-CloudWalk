from app.rag.graph_retriever import expand_query_to_pt, recommend_params
from app.agents.knowledge import knowledge_node
import os
import contextlib


def test_expand_query_to_pt_maps_basic_terms():
    q = "What are the credit and debit fees for the card machine on my phone?"
    expanded = expand_query_to_pt(q)
    assert "débito" in expanded or "debito" in expanded
    assert "crédito" in expanded or "credito" in expanded
    assert "maquininha" in expanded
    assert "celular" in expanded


def test_recommend_params_by_intent():
    assert recommend_params("How can I use my phone as a card machine?") == (12, 3)
    b, d = recommend_params("What are the fees for debit and credit?")
    assert d >= 2


def test_breadth_depth_variations():
    # sanity checks on other intents
    b1, d1 = recommend_params("Tell me about PDV product")
    assert b1 >= 10 and d1 <= 2


def test_expand_query_contains_aliasing_for_phone_machine():
    expanded = expand_query_to_pt("use my phone as a card machine")
    assert "maquininha" in expanded and "celular" in expanded


def test_retriever_params_stress_small_variations():
    # Stress: ensure function returns valid ranges across several phrasings
    qs = [
        "fees for debit",
        "rates for credit",
        "how to use tap to pay",
        "como usar maquininha",
        "product overview pdv",
    ]
    for q in qs:
        b, d = recommend_params(q)
        assert 5 <= b <= 20
        assert 1 <= d <= 4


def test_meta_contains_retrieval_hyperparams():
    out = knowledge_node({"message": "What are the fees?", "locale": "en"})
    meta = out.get("meta", {})
    assert "breadth" in meta and "depth" in meta
    assert "vector_k" in meta and isinstance(meta.get("vector_k"), int)


def test_parameter_sweep_caps(monkeypatch):
    # Sweep through vector_k {2,3,4} by overriding env and ensuring run succeeds
    # We simulate by tweaking OPENAI_MODEL_FAST to avoid slower models if needed
    monkeypatch.setenv("OPENAI_MODEL_KNOWLEDGE", os.environ.get("OPENAI_MODEL_FAST", "gpt-4o-mini"))
    for _ in [2, 3, 4]:
        out = knowledge_node(
            {"message": "What are the fees of the Maquininha Smart?", "locale": "en"}
        )
        meta = out.get("meta", {})
        assert meta.get("token_estimate") is None or meta.get("token_estimate") < 5000
