from app.rag.graph_retriever import expand_query_to_pt, recommend_params


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
