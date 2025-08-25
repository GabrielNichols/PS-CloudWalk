from __future__ import annotations

import re
import os
import sys
from typing import List, Dict

# Ensure project root is importable when running as a script (python scripts/eval_rag.py)
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from neo4j import GraphDatabase
from app.settings import settings
from app.rag.embeddings import get_embeddings
from app.rag.vectorstore import Neo4jVectorStore
import numpy as np
from app.rag.graph_retriever import expand_query_to_pt
from app.rag.graphrag_baseline import GraphRAGBaseline
from langsmith import Client, traceable
import uuid
from dotenv import load_dotenv


DATASET: List[Dict] = [
    {
        "question": "Quais as taxas de débito e crédito?",
        "expect_contains": ["débito", "crédito"],
        "tags": ["fees"],
    },
    {
        "question": "Quanto custa a Maquininha Smart?",
        "expect_contains": ["Maquininha", "Smart"],
        "tags": ["product"],
    },
    {
        "question": "Como usar o celular como maquininha?",
        "expect_contains": ["Tap", "celular"],
        "tags": ["howto"],
    },
    {
        "question": "What are the fees of the Maquininha Smart?",
        "expect_contains": ["fee", "Smart"],
        "tags": ["fees"],
    },
    {
        "question": "What is the cost of the Maquininha Smart?",
        "expect_contains": ["cost", "Smart"],
        "tags": ["product"],
    },
    {
        "question": "What are the rates for debit and credit card transactions?",
        "expect_contains": ["debit", "credit"],
        "tags": ["fees"],
    },
    {
        "question": "How can I use my phone as a card machine?",
        "expect_contains": ["phone", "card"],
        "tags": ["howto"],
    },
]


def _connect_driver():
    uri = settings.neo4j_uri or (
        f"neo4j+s://{settings.aura_instanceid}.databases.neo4j.io"
        if settings.aura_instanceid
        else None
    )
    if not uri:
        raise RuntimeError("Neo4j URI missing")
    if not settings.neo4j_username or not settings.neo4j_password:
        raise RuntimeError("Neo4j credentials missing")
    return GraphDatabase.driver(uri, auth=(settings.neo4j_username, settings.neo4j_password))


def ensure_fulltext_index():
    driver = _connect_driver()
    db = settings.neo4j_database or "neo4j"
    with driver.session(database=db) as s:
        s.run(
            "CREATE FULLTEXT INDEX entityIdx IF NOT EXISTS FOR (n:Product|Feature|Fee|HowTo) ON EACH [n.name]"
        ).consume()
    driver.close()


def score_graph(question: str) -> float:
    driver = _connect_driver()
    db = settings.neo4j_database or "neo4j"
    with driver.session(database=db) as s:
        rows = s.run(
            "CALL db.index.fulltext.queryNodes('entityIdx', $q) YIELD node, score "
            "RETURN node.name AS name, labels(node) AS labels, score ORDER BY score DESC LIMIT 5",
            q=expand_query_to_pt(question),
        ).data()
    driver.close()
    # simple coverage score: proportion of tokens matched in names
    toks = [t for t in re.split(r"\W+", question.lower()) if len(t) > 3]
    if not rows:
        return 0.0
    hits = 0
    for r in rows:
        name = (r.get("name") or "").lower()
        hits += sum(1 for t in toks if t in name)
    return min(1.0, hits / max(1, len(toks)))


def score_vector(question: str) -> float:
    emb = get_embeddings()
    retriever = Neo4jVectorStore.connect_retriever(embedding=emb, k=5)
    if retriever is None:
        return 0.0
    docs = retriever.invoke(question)
    # cosine similarity between question and each chunk
    try:
        # langchain community OpenAIEmbeddings: embed_documents and embed_query
        q_vec = emb.embed_query(question)
        d_vecs = emb.embed_documents([d.page_content for d in docs]) if docs else []
        if not d_vecs:
            return 0.0

        def cos(a, b):
            a = np.array(a)
            b = np.array(b)
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

        sims = [cos(q_vec, dv) for dv in d_vecs]
        # Normalize to 0-1 assuming cosine in [-1,1]
        return max(0.0, (max(sims) + 1.0) / 2.0)
    except Exception:
        # fallback to overlap if embed_query not available
        joined = "\n".join([d.page_content.lower() for d in docs])
        toks = [t for t in re.split(r"\W+", question.lower()) if len(t) > 3]
        hits = sum(1 for t in toks if t in joined)
        return min(1.0, hits / max(1, len(toks)))


def _strip_quotes(val: str | None) -> str | None:
    if not val:
        return val
    v = val.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    return v


@traceable(name="rag_eval_run")
def run():
    # Load env and sanitize for LangSmith
    load_dotenv(override=False)
    for k in [
        "LANGSMITH_API_KEY",
        "LANGSMITH_TRACING",
        "LANGSMITH_PROJECT",
        "LANGSMITH_ENDPOINT",
        "LANGCHAIN_PROJECT",
        "LANGCHAIN_TRACING_V2",
        "LANGCHAIN_ENDPOINT",
    ]:
        v = _strip_quotes(os.environ.get(k))
        if v is not None:
            os.environ[k] = v
    ensure_fulltext_index()
    results = []
    # Only init Client if API key is present
    ls = Client() if os.environ.get("LANGSMITH_API_KEY") else None
    # Choose experiment name from env or default
    experiment_name = (
        os.environ.get("LS_EXPERIMENT_NAME")
        or os.environ.get("LANGSMITH_EXPERIMENT")
        or "RAG-PSCloudWalk-v1"
    )
    experiment_run_id = str(uuid.uuid4())
    import time

    for item in DATASET:
        q = item["question"]
        g_start = time.perf_counter()
        g = score_graph(q)
        g_ms = int((time.perf_counter() - g_start) * 1000)
        v_start = time.perf_counter()
        v = score_vector(q)
        v_ms = int((time.perf_counter() - v_start) * 1000)
        # Baseline via neo4j-graphrag
        base_start = time.perf_counter()
        try:
            baseline = GraphRAGBaseline()
            base_res = baseline.search(q, top_k=5, return_context=True)
            base_ms = int((time.perf_counter() - base_start) * 1000)
            base_answer = base_res.get("answer")
            base_ctx_len = len(str(base_res.get("context") or ""))
        except Exception:
            base_ms = 0
            base_answer = None
            base_ctx_len = 0
        finally:
            try:
                baseline.close()
            except Exception:
                pass

        row = {
            "q": q,
            "graph": round(g, 3),
            "graph_ms": g_ms,
            "vector": round(v, 3),
            "vector_ms": v_ms,
            "baseline_ms": base_ms,
            "baseline_has_answer": bool(base_answer),
            "baseline_ctx_len": base_ctx_len,
        }
        results.append(row)
        if ls is not None:
            try:
                # Log per-item feedback in LangSmith
                ls.create_feedback(
                    run_id=experiment_run_id,
                    key="rag-graph",
                    score=g,
                    comment=q,
                    metadata={"latency_ms": g_ms},
                    source_info={"type": "eval", "question": q, "experiment": experiment_name},
                )
                ls.create_feedback(
                    run_id=experiment_run_id,
                    key="rag-vector",
                    score=v,
                    comment=q,
                    metadata={"latency_ms": v_ms},
                    source_info={"type": "eval", "question": q, "experiment": experiment_name},
                )
                ls.create_feedback(
                    run_id=experiment_run_id,
                    key="graphrag-baseline",
                    score=1.0 if base_answer else 0.0,
                    comment=q,
                    metadata={"latency_ms": base_ms, "ctx_len": base_ctx_len},
                    source_info={"type": "eval", "question": q, "experiment": experiment_name},
                )
            except Exception as e:
                print("Error creating feedback:", e)
    print("RAG retrieval coverage (0-1):")
    for r in results:
        print(f"- {r['q']}: graph={r['graph']} vector={r['vector']}")
    gavg = sum(r["graph"] for r in results) / len(results)
    vavg = sum(r["vector"] for r in results) / len(results)
    print(f"Averages: graph={gavg:.3f} vector={vavg:.3f}")


if __name__ == "__main__":
    # Ensure project root is importable when executed via `python scripts/eval_rag.py`
    import sys, os

    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    run()
