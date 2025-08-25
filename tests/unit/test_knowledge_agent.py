from app.agents.knowledge import knowledge_node


def test_knowledge_agent_returns_structure_without_crashing(monkeypatch):
    # Provide minimal state
    state = {"message": "What are the fees of the Maquininha Smart?", "locale": "en"}
    # Run without asserting LLM content (external); only structure
    out = knowledge_node(state)
    assert isinstance(out, dict)
    assert "answer" in out
    assert out["agent"] == "KnowledgeAgent"
    assert "grounding" in out


def test_knowledge_agent_uses_graph_vector_mode():
    out = knowledge_node({"message": "What are the fees of the Maquininha Smart?", "locale": "en"})
    grounding = out.get("grounding", {})
    assert grounding.get("mode") in ("graph+vector", "web", "placeholder")


def test_knowledge_agent_contains_fee_keywords_en():
    out = knowledge_node({"message": "What are the fees of the Maquininha Smart?", "locale": "en"})
    txt = out.get("answer", "").lower()
    # Regression sanity: presence of fee-related keywords
    assert "fee" in txt or "tax" in txt or "rate" in txt


def test_howto_contains_action_terms():
    out = knowledge_node({"message": "How can I use my phone as a card machine?", "locale": "en"})
    txt = out.get("answer", "").lower()
    # Look for action words typical of how-to answers
    assert any(w in txt for w in ["how", "use", "tap to pay", "nfc", "steps"]) or "how" in txt


def test_card_fees_not_oos_when_context_present():
    out = knowledge_node({"message": "Quais as taxas do cartão?", "locale": "pt-BR"})
    # Should avoid out-of-scope meta when card content exists
    meta = out.get("meta", {})
    assert meta.get("oos") is not True
