from app.agents.knowledge.knowledge_node import knowledge_node
from langsmith import traceable


@traceable(name="Test.Knowledge.Structure", metadata={"test_type": "unit", "agent": "knowledge"})
def test_knowledge_agent_returns_structure_without_crashing(monkeypatch):
    """Test basic knowledge agent structure and response format."""
    state = {"message": "What are the fees of the Maquininha Smart?", "locale": "en"}

    # Mock external dependencies to avoid actual LLM calls
    def mock_web_search(*args, **kwargs):
        return []

    def mock_get_embeddings():
        from langchain_community.embeddings import FakeEmbeddings
        return FakeEmbeddings(size=3072)

    monkeypatch.setattr("app.tools.web_search.web_search", mock_web_search)
    monkeypatch.setattr("app.rag.embeddings.get_embeddings", mock_get_embeddings)

    out = knowledge_node(state)
    assert isinstance(out, dict)
    assert "answer" in out
    assert out["agent"] == "KnowledgeAgent"
    assert "grounding" in out
    assert "meta" in out


@traceable(name="Test.Knowledge.Mode", metadata={"test_type": "unit", "agent": "knowledge"})
def test_knowledge_agent_uses_correct_mode():
    """Test that knowledge agent uses correct retrieval mode."""
    out = knowledge_node({"message": "What are the fees of the Maquininha Smart?", "locale": "en"})
    grounding = out.get("grounding", {})
    assert grounding.get("mode") in ("vector+faq", "web", "placeholder", "none")

@traceable(name="Test.Knowledge.Content", metadata={"test_type": "unit", "agent": "knowledge"})
def test_knowledge_agent_content_quality():
    """Test that knowledge agent returns relevant content."""
    out = knowledge_node({"message": "What are the fees of the Maquininha Smart?", "locale": "en"})
    txt = out.get("answer", "").lower()

    # Check for relevant keywords in response
    relevant_terms = ["fee", "tax", "rate", "maquininha", "smart"]
    has_relevant_content = any(term in txt for term in relevant_terms)

    # Either has relevant terms or indicates it doesn't know (which is also valid)
    assert has_relevant_content or "don't know" in txt or "não sei" in txt
