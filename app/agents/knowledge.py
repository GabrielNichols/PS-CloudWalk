from typing import Dict, Any
import time
from app.graph.helpers import sget, sget_meta
from app.rag.vector_retriever import VectorRAGRetriever
from app.rag.embeddings import get_embeddings
from app.tools.web_search import web_search
from app.settings import settings
from openai import OpenAI
from app.graph.guardrails import system_prompt
from langsmith import traceable
from langsmith.wrappers import wrap_openai


from app.rag.graph_retriever import graph_retrieve, recommend_params
from concurrent.futures import ThreadPoolExecutor
from app.rag.vectorstore import Neo4jVectorStore
from typing import Optional


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
    llm_latency_ms = 0
    total_start = time.perf_counter()

    # Parallel vector + graph retrieval using threads (safe for sync contexts)
    vector_docs = []
    vector_sources: list[dict] = []
    rows = []
    graph_urls_list: list[str] = []
    b, dpth = 10, 2
    min_score = float(getattr(settings, "rag_fulltext_min_score", 0.0) or 0.0)

    q_lower = (question or "").lower()
    # Single vector k (configurável por env), sem regras de assunto
    vector_k = int(settings.rag_vector_k or 3)

    # Cache retrievers to avoid reconnect overhead
    global _VEC_RET  # type: ignore[name-defined]
    global _FAQ_RET  # type: ignore[name-defined]
    try:
        _VEC_RET
    except NameError:
        _VEC_RET = None  # type: ignore[assignment]
    try:
        _FAQ_RET
    except NameError:
        _FAQ_RET = None  # type: ignore[assignment]

    def _vector_sync():
        docs_local = []
        sources_local: list[dict] = []
        t0 = time.perf_counter()
        emb = get_embeddings()
        if not emb:
            return docs_local, sources_local, 0
        retriever = _VEC_RET or VectorRAGRetriever(embedding=emb, k=vector_k)
        _set_cached = _VEC_RET is None
        if _set_cached:
            _VEC_RET = retriever
        try:
            docs_local = retriever.retrieve(question)
            sources_local = [
                {"type": "page", "url": d.metadata.get("url") or d.metadata.get("source")}
                for d in docs_local
                if isinstance(d.metadata, dict)
            ]
            # RAG clean: rely solely on indexed vector store (no external fetches)
        except Exception as e:
            docs_local = []
            sources_local = []
            return [], [], int((time.perf_counter() - t0) * 1000)
        ms = int((time.perf_counter() - t0) * 1000)
        return docs_local, sources_local, ms

    def _graph_sync():
        t0 = time.perf_counter()
        try:
            _b, _d = recommend_params(question)
            rows_local, urls_local = graph_retrieve(
                question, breadth=_b, depth=_d, min_score=min_score
            )
            ms = int((time.perf_counter() - t0) * 1000)
            return rows_local, urls_local, _b, _d, ms
        except Exception:
            return [], [], 10, 2, 0

    def _faq_vector_sync():
        t0 = time.perf_counter()
        try:
            emb = get_embeddings()
            if not emb:
                return [], 0
            faq_ret = _FAQ_RET or Neo4jVectorStore.connect_faq_retriever(embedding=emb, k=2)
            if not faq_ret:
                return [], 0
            if _FAQ_RET is None:
                _FAQ_RET = faq_ret
            docs = faq_ret.invoke(question)
            ms = int((time.perf_counter() - t0) * 1000)
            return docs, ms
        except Exception as e:
            return [], int((time.perf_counter() - t0) * 1000)

    with ThreadPoolExecutor(max_workers=3) as ex:
        vf = ex.submit(_vector_sync)
        gf = ex.submit(_graph_sync)
        ff = ex.submit(_faq_vector_sync)
        vector_timeout = False
        graph_timeout = False
        faq_timeout = False
        try:
            vector_docs, vector_sources, vector_ms = vf.result(timeout=3.0)
        except Exception:
            vector_docs, vector_sources, vector_ms = [], [], 0
            vector_timeout = True
        try:
            rows, graph_urls_list, b, dpth, graph_ms = gf.result(timeout=2.8)
        except Exception:
            rows, graph_urls_list, b, dpth, graph_ms = [], [], 10, 2, 0
            graph_timeout = True
        try:
            faq_docs, faq_ms = ff.result(timeout=0.8)
        except Exception:
            faq_docs, faq_ms = [], 0
            faq_timeout = True

    # 3) Combine graph facts and vector documents (with minimal context window)
    vector_text = "\n\n".join([d.page_content for d in vector_docs]) if vector_docs else ""
    faq_text = "\n\n".join([d.page_content for d in (faq_docs or [])])
    facts_txt = []
    for row in rows or []:
        entity = row.get("entity")
        labels = ",".join(row.get("labels") or [])
        clean_facts = [
            f for f in (row.get("facts") or []) if f and f.get("rel") and f.get("target")
        ]
        facts = "; ".join([f"{f['rel']} {f['target']}" for f in clean_facts])
        facts_txt.append(f"{entity} [{labels}]: {facts}")
    graph_text = "\n".join(facts_txt)
    vec_urls = [s.get("url") for s in vector_sources if isinstance(s, dict) and s.get("url")]
    graph_urls = list(graph_urls_list or [])
    all_sources_urls = set([str(u) for u in vec_urls]) | set([str(u) for u in graph_urls])

    # Keep simple deterministic ordering to avoid biasing retrieval results
    prioritized_urls = sorted(list(all_sources_urls))
    # Truncate to keep prompt within budget and reduce latency
    max_section = int(settings.rag_max_context_chars or 2000)
    # Dynamic allocation: if no graph facts, favor vector; else prioritize graph
    if graph_text.strip():
        gshare, fshare, vshare = 0.7, 0.15, 0.15
    else:
        gshare, fshare, vshare = 0.1, 0.2, 0.7
    gtxt = graph_text[: int(max_section * gshare)]
    ftxt = faq_text[: int(max_section * fshare)]
    vtxt = vector_text[: int(max_section * vshare)]
    build_start = time.perf_counter()
    combined_context = (
        "[GRAPH FACTS]\n" + gtxt + "\n\n[FAQ]\n" + ftxt + "\n\n[DOCUMENTS]\n" + vtxt
    ).strip()
    build_ms = int((time.perf_counter() - build_start) * 1000)
    g_len = len(gtxt)
    f_len = len(ftxt)
    v_len = len(vtxt)

    # Lightweight confidence proxy: presence of both graph facts and vector docs
    has_graph = bool(graph_text.strip())
    has_vector = bool(vector_text.strip())
    has_faq = bool(faq_text.strip())
    # Heuristic ensemble confidence using configurable weights
    gw = float(settings.rag_graph_weight or 0.6)
    vw = float(settings.rag_vector_weight or 0.4)
    confidence = (
        (gw if has_graph else 0.0) + (vw if has_vector else 0.0) + (0.2 if has_faq else 0.0)
    )

    if combined_context:
        client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        client = wrap_openai(client) if client else None
        if client is not None:
            # Emphasize graph as primary, vector as supporting details
            prompt = (
                system_prompt("knowledge", sget(state, "locale"))
                + "\n\nPrimary context is [GRAPH FACTS]; use [DOCUMENTS] only to complement or verify."
                + " If context is insufficient, say you don't know."
                + f"\n\nQuestion: {question}\n\nContext:\n{combined_context}"
            )
            llm_start = time.time()
            completion = client.chat.completions.create(
                model=(
                    settings.openai_model_knowledge
                    or settings.openai_model_fast
                    or settings.openai_model
                ),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            final_answer = completion.choices[0].message.content or ""
            if not final_answer:
                # fallback to answering directly from facts to avoid null outputs in traces
                final_answer = (
                    "Based on the context: "
                    + (gtxt[:300] or vtxt[:300] or ftxt[:300] or "No context")
                )
            llm_latency_ms = int((time.time() - llm_start) * 1000)
        else:
            final_answer = combined_context[:1000]
        # Decide whether to attach sources. If the answer é um "não sei"/out-of-scope,
        # suprima as fontes e marque baixa confiança.
        lower_ans = (final_answer or "").lower()
        out_of_scope_phrases = [
            "i don't know",
            "i do not know",
            "não tenho informações",
            "não sei",
            "fora do escopo",
        ]
        is_oos = any(p in lower_ans for p in out_of_scope_phrases)
        attach_sources = bool(all_sources_urls) and not is_oos and ("sources:" not in lower_ans)
        if attach_sources:
            # Ensure join receives List[str]
            selected = prioritized_urls[: int(getattr(settings, "rag_sources_max", 3) or 3)]
            final_answer += "\n\nSources: " + ", ".join(selected)
        # Pick a mode even if sources list is empty, to signal hybrid retrieval
        mode_value = "graph+vector" if (has_graph or has_vector or has_faq) else ("none")
        return {
            "answer": final_answer,
            "agent": "KnowledgeAgent",
            "grounding": {
                "mode": mode_value,
                "sources": list(all_sources_urls) if attach_sources else [],
                # confidence reflects evidence presence even if we didn't attach URLs
                "confidence": confidence,
            },
            "meta": {
                **base_meta,
                **meta,
                "locale": sget(state, "locale"),
                "breadth": b,
                "depth": dpth,
                "vector_k": vector_k,
                "urls_count": len(all_sources_urls),
                "llm": settings.openai_model,
                "latency_ms": llm_latency_ms,
                "token_estimate": int((len(combined_context) + len(question)) / 4),
                "oos": is_oos,
                "attached_sources": attach_sources,
                "min_score": min_score,
                "has_faq": has_faq,
                # retrieval metrics
                "vector_ms": vector_ms,
                "graph_ms": graph_ms,
                "faq_ms": faq_ms,
                "build_ms": build_ms,
                "total_ms": int((time.perf_counter() - total_start) * 1000),
                "vector_docs_count": len(vector_docs or []),
                "graph_rows_count": len(rows or []),
                "faq_docs_count": len(faq_docs or []),
                # urls for debugging
                "vector_urls": vec_urls[:5],
                "graph_urls": graph_urls[:5],
                "selected_sources": prioritized_urls[: int(getattr(settings, "rag_sources_max", 3) or 3)],
                "timeouts": {
                    "vector": vector_timeout,
                    "graph": graph_timeout,
                    "faq": faq_timeout,
                },
                "section_lengths": {"graph": g_len, "faq": f_len, "docs": v_len},
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
    # If KnowledgeAgent explicitly flagged out-of-scope, do NOT handoff to custom; end with personality
    meta = state.get("meta") if isinstance(state, dict) else getattr(state, "meta", {})
    if isinstance(meta, dict) and meta.get("oos") is True:
        decision = "personality"
        if isinstance(state, dict):
            meta.update(
                {
                    "handoff_confidence": conf,
                    "handoff_threshold": None,
                    "handoff_decision": decision,
                }
            )
            state["meta"] = meta
        return decision
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
