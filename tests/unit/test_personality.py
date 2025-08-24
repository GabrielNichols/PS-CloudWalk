from app.agents.personality import personality_node


def test_personality_prefix_en():
    state = {"answer": "Hello", "locale": "en"}
    out = personality_node(state)
    assert out["answer"].startswith("[en]")


def test_personality_prefix_pt():
    state = {"answer": "Oi", "locale": "pt-BR"}
    out = personality_node(state)
    assert out["answer"].startswith("[pt-BR]")
