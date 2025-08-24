from typing import Dict, Any
from app.graph.helpers import sget, sget_meta
from app.rag.vectorstore import Neo4jVectorStore
from app.rag.embeddings import get_embeddings
from app.tools.web_search import web_search
from app.settings import settings
from openai import OpenAI
from app.graph.guardrails import system_prompt
from langsmith import traceable
from langsmith.wrappers import wrap_openai


from app.rag.graph_retriever import graph_retrieve, recommend_params


INFINITEPAY_URLS = [
    "https://www.infinitepay.io",
    "https://www.infinitepay.io/maquininha",
    "https://www.infinitepay.io/maquininha-celular",
    "https://www.infinitepay.io/tap-to-pay",
    "https://www.infinitepay.io/pdv",
    "https://www.infinitepay.io/receba-na-hora",
    "https://www.infinitepay.io/gestao-de-cobranca-2",
    "https://www.infinitepay.io/link-de-pagamento",
    "https://www.infinitepay.io/loja-online",
    "https://www.infinitepay.io/boleto",
    "https://www.infinitepay.io/conta-digital",
    "https://www.infinitepay.io/pix",
    "https://www.infinitepay.io/emprestimo",
    "https://www.infinitepay.io/cartao",
    "https://www.infinitepay.io/rendimento",
]


@traceable(name="KnowledgeAgent")
def knowledge_node(state: Dict[str, Any]) -> Dict[str, Any]:
    question = sget(state, "message", "")
    meta = {"agent": "KnowledgeAgent"}
    base_meta = sget_meta(state)

    # 1) Vector retrieval
    vector_docs = []
    vector_sources: list[dict] = []
    emb = get_embeddings()
    if emb:
        retriever = Neo4jVectorStore.connect_retriever(embedding=emb, k=5)
        if retriever:
            try:
                vector_docs = retriever.invoke(question)
                vector_sources = [
                    {"type": "page", "url": d.metadata.get("url") or d.metadata.get("source")}
                    for d in vector_docs
                    if isinstance(d.metadata, dict)
                ]
            except Exception:
                vector_docs = []

    # 2) Graph retrieval with breadth/depth and EN->PT normalization
    try:
        b, dpth = recommend_params(question)
        rows, graph_urls_list = graph_retrieve(question, breadth=b, depth=dpth)
    except Exception:
        rows, graph_urls_list = [], []

    # 3) Combine graph facts and vector documents
    vector_text = "\n\n".join([d.page_content for d in vector_docs]) if vector_docs else ""
    facts_txt = []
    for row in rows or []:
        entity = row.get("entity")
        labels = ",".join(row.get("labels") or [])
        facts = "; ".join([f"{f['rel']} {f['target']}" for f in row.get("facts") or []])
        facts_txt.append(f"{entity} [{labels}]: {facts}")
    graph_text = "\n".join(facts_txt)
    vec_urls = [s.get("url") for s in vector_sources if isinstance(s, dict) and s.get("url")]
    graph_urls = list(graph_urls_list or [])
    all_sources_urls = set([str(u) for u in vec_urls]) | set([str(u) for u in graph_urls])
    combined_context = ("[GRAPH FACTS]\n" + graph_text + "\n\n[DOCUMENTS]\n" + vector_text).strip()

    # Lightweight confidence proxy: presence of both graph facts and vector docs
    has_graph = bool(graph_text.strip())
    has_vector = bool(vector_text.strip())
    confidence = 1.0 if (has_graph and has_vector) else 0.5 if (has_graph or has_vector) else 0.0

    if combined_context:
        client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        client = wrap_openai(client) if client else None
        if client is not None:
            prompt = (
                system_prompt("knowledge", sget(state, "locale"))
                + "\n\nUse the facts and documents below. If insufficient, say you don't know."
                + f"\n\nQuestion: {question}\n\nContext:\n{combined_context[:12000]}"
            )
            completion = client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            final_answer = completion.choices[0].message.content or ""
        else:
            final_answer = combined_context[:1000]
        if all_sources_urls:
            # Ensure join receives List[str]
            srcs = [str(u) for u in sorted(all_sources_urls)]
            final_answer += "\n\nSources: " + ", ".join(srcs[:5])
        return {
            "answer": final_answer,
            "agent": "KnowledgeAgent",
            "grounding": {
                "mode": "graph+vector",
                "sources": list(all_sources_urls),
                "confidence": confidence,
            },
            "meta": {
                **base_meta,
                **meta,
                "locale": sget(state, "locale"),
                "breadth": b,
                "depth": dpth,
                "vector_k": 5,
                "urls_count": len(all_sources_urls),
                "llm": settings.openai_model,
            },
        }

    # 4) Fallback: web search for open-domain
    results = web_search(question, k=3)
    if results:
        grounding_sources = [
            {"type": "web", "url": r.get("url") or r.get("source")} for r in results
        ]
        answer = "Using web search fallback for open-domain queries."
        return {
            "answer": answer,
            "agent": "KnowledgeAgent",
            "grounding": {"mode": "web", "sources": grounding_sources, "confidence": 0.3},
            "meta": {**base_meta, **meta},
        }

    # 5) Final fallback: static URLs
    answer = (
        "KnowledgeAgent placeholder: RAG will answer grounded by InfinitePay pages. "
        "For now, this is a stub response."
    )
    grounding = {
        "mode": "placeholder",
        "sources": [{"url": u, "type": "page"} for u in INFINITEPAY_URLS[:2]],
    }
    return {
        "answer": answer,
        "agent": "KnowledgeAgent",
        "grounding": grounding,
        "meta": {**base_meta, **meta},
    }


@traceable(name="KnowledgeNext")
def knowledge_next(state: Dict[str, Any]) -> str:
    """Decide next step based on confidence: handoff to custom if low."""
    grounding = (
        state.get("grounding") if isinstance(state, dict) else getattr(state, "grounding", {})
    )
    try:
        conf = float((grounding or {}).get("confidence") or 0.0)
    except Exception:
        conf = 0.0
    # threshold da env, default 0.45
    th = settings.handoff_threshold if settings.handoff_threshold is not None else 0.45
    # logging simples no meta
    decision = "custom" if conf < th else "personality"
    # anexar pistas no meta para análise
    if isinstance(state, dict):
        meta = state.get("meta", {}) or {}
        meta.update(
            {"handoff_confidence": conf, "handoff_threshold": th, "handoff_decision": decision}
        )
        state["meta"] = meta
    return decision
