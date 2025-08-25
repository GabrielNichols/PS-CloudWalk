from __future__ import annotations

from typing import Dict, List, Tuple
from neo4j import GraphDatabase
from app.settings import settings


EN_TO_PT: Dict[str, List[str]] = {
    "debit": ["débito"],
    "credit": ["crédito"],
    "fees": ["taxas", "tarifas"],
    "rates": ["taxas", "tarifas"],
    "phone": ["celular"],
    "card machine": ["maquininha"],
    "card": ["cartão"],
    "card fees": ["taxas do cartão", "anuidade", "taxa de adesão"],
    "cost": ["custo", "preço"],
    "smart": ["smart"],
}


def expand_query_to_pt(question: str) -> str:
    q = question.lower()
    terms: List[str] = [question]
    for en, pts in EN_TO_PT.items():
        if en in q:
            terms.extend(pts)
    # Join as a single string for fulltext; Neo4j query parser will tokenize
    return " ".join(terms)


def _driver():
    uri = settings.neo4j_uri or (
        f"neo4j+s://{settings.aura_instanceid}.databases.neo4j.io"
        if settings.aura_instanceid
        else None
    )
    if not (uri and settings.neo4j_username and settings.neo4j_password):
        raise RuntimeError("Neo4j connection not configured")
    return GraphDatabase.driver(uri, auth=(settings.neo4j_username, settings.neo4j_password))


def graph_retrieve(
    question: str, breadth: int = 10, depth: int = 2, min_score: float = 0.0
) -> Tuple[List[Dict], List[str]]:
    """Fast Cypher retriever inspired by GraphRAG patterns.

    1) Seed with FULLTEXT (entityIdx) → top-k nodes by score
    2) Expand facts up to `depth` using explicit hops (avoids variable-length path explosion)
    3) Collect related Page URLs for explainability/citations

    Returns rows: [{entity, labels, facts:[{rel,target}, ...]}], urls: [str]
    """
    driver = _driver()
    db = settings.neo4j_database or "neo4j"
    q_pt = expand_query_to_pt(question)
    rel_types = "HAS_FEATURE|HAS_FEE|HAS_HOWTO"

    # Build Cypher dynamically to keep it efficient for depth 1–3
    base = [
        "CALL db.index.fulltext.queryNodes('entityIdx', $q) YIELD node, score",
        "WITH node, score WHERE score >= $min_score",
        "ORDER BY score DESC LIMIT $b",
        "WITH collect(node)[0..$b] AS seeds",
        "UNWIND seeds AS n",
    ]

    # depth 1 facts
    d1 = [
        f"OPTIONAL MATCH (n)-[r1:{rel_types}]->(t1)",
        "WITH n, collect({rel:type(r1), target:coalesce(t1.name, t1.canonical_name)})[0..$b] AS f1",
    ]

    # depth 2 facts (optional)
    if depth and depth >= 2:
        d2 = [
            f"OPTIONAL MATCH (n)-[:{rel_types}]->(m1)-[r2:{rel_types}]->(t2)",
            "WITH n, f1 AS f1_keep, collect({rel:type(r2), target:coalesce(t2.name, t2.canonical_name)})[0..$b] AS c2",
            "WITH n, f1_keep + c2 AS f2",
        ]
    else:
        d2 = ["WITH n, f1 AS f2"]

    # depth 3 facts (optional)
    if depth and depth >= 3:
        d3 = [
            f"OPTIONAL MATCH (n)-[:{rel_types}]->(m1)-[:{rel_types}]->(m2)-[r3:{rel_types}]->(t3)",
            "WITH n, f2 AS f2_keep, collect({rel:type(r3), target:coalesce(t3.name, t3.canonical_name)})[0..$b] AS c3",
            "WITH n, f2_keep + c3 AS facts",
        ]
    else:
        d3 = ["WITH n, f2 AS facts"]

    tail = [
        "WITH n, facts",
        "OPTIONAL MATCH (n)-[:DESCRIBED_ON]->(pg:Page)",
        "OPTIONAL MATCH (fq:FAQ)<-[:HAS_FAQ]-(pg2:Page)-[:MENTIONS]->(n)",
        "WITH n, facts, collect(DISTINCT pg.url)+collect(DISTINCT pg2.url) AS rawUrls",
        "WITH n, facts, [u IN rawUrls WHERE u IS NOT NULL][0..$b] AS urls",
        "RETURN n.name AS entity, labels(n) AS labels, facts, urls",
    ]

    cypher = "\n".join(base + d1 + d2 + d3 + tail)

    with driver.session(database=db) as s:
        rows = s.run(cypher, q=q_pt, b=breadth, min_score=min_score).data()
    driver.close()
    urls: List[str] = []
    for r in rows:
        urls.extend(r.get("urls") or [])
    urls = list(dict.fromkeys([u for u in urls if u]))
    return rows, urls


def recommend_params(question: str) -> Tuple[int, int]:
    q = (question or "").lower()
    if any(k in q for k in ["how ", "como ", "como usar", "how do i", "how can i", "how to"]):
        return 12, 3
    if any(k in q for k in ["fee", "fees", "taxa", "tarifa", "rate", "rates", "pricing", "cost"]):
        return 12, 2
    # product/overview
    return 15, 1
