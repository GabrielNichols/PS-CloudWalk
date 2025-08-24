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
