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
    question: str, breadth: int = 10, depth: int = 2
) -> Tuple[List[Dict], List[str]]:
    driver = _driver()
    db = settings.neo4j_database or "neo4j"
    q_pt = expand_query_to_pt(question)
    rel_types = "HAS_FEATURE|HAS_FEE|HAS_HOWTO"
    depth_clause = f"1..{max(1, depth)}"
    cypher = (
        "CALL db.index.fulltext.queryNodes('entityIdx', $q) YIELD node, score "
        "WITH node, score ORDER BY score DESC LIMIT $b "
        f"OPTIONAL MATCH (node)-[r:{rel_types}*{depth_clause}]->(o) "
        "WITH node, [rel IN r | type(rel)] AS rels, collect(o)[0..$b] AS objs "
        "RETURN node.name AS entity, labels(node) AS labels, "
        "[x IN range(0, size(objs)-1) | {rel: rels[x], target: objs[x].name}] AS facts"
    )
    rows: List[Dict]
    with driver.session(database=db) as s:
        rows = s.run(cypher, q=q_pt, b=breadth).data()
        url_rows = s.run(
            "MATCH (pg:Page)-[:MENTIONS]->(n) WHERE n.name IN $names RETURN pg.url AS url",
            names=[r.get("entity") for r in rows if r.get("entity")],
        ).data()
    driver.close()
    urls = [r.get("url") for r in url_rows if r.get("url")]
    return rows, urls


def recommend_params(question: str) -> Tuple[int, int]:
    q = (question or "").lower()
    if any(k in q for k in ["how ", "como ", "como usar", "how do i", "how can i", "how to"]):
        return 12, 3  # breadth, depth for how-to style
    if any(k in q for k in ["fee", "taxa", "tarifa", "rate", "rates"]):
        return 12, 2
    # product/overview
    return 15, 1
