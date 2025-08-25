from __future__ import annotations

import os
import sys
from typing import List, Dict
import html
from urllib.parse import urlparse

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from neo4j import GraphDatabase
from app.settings import settings


def _driver():
    uri = settings.neo4j_uri or (
        f"neo4j+s://{settings.aura_instanceid}.databases.neo4j.io"
        if settings.aura_instanceid
        else None
    )
    if not uri:
        raise RuntimeError("Neo4j URI not configured")
    if not settings.neo4j_username or not settings.neo4j_password:
        raise RuntimeError("Neo4j credentials not configured")
    return GraphDatabase.driver(uri, auth=(settings.neo4j_username, settings.neo4j_password))


def fetch_triplets(limit: int = 200) -> List[Dict]:
    cypher = (
        "MATCH (p:Page)-[r:HAS_FAQ]->(f:FAQ) "
        "MATCH (p)-[m:MENTIONS]->(pr:Product) "
        "RETURN p.url AS url, f.question AS q, pr.name AS product LIMIT $lim"
    )
    drv = _driver()
    db = settings.neo4j_database or "neo4j"
    with drv.session(database=db) as s:
        rows = s.run(cypher, lim=limit).data()
    drv.close()
    return rows


def to_mermaid(rows: List[Dict]) -> str:
    # Canonical maps with compact IDs (P1, F1, PR1)
    page_ids: Dict[str, str] = {}
    faq_ids: Dict[str, str] = {}
    prod_ids: Dict[str, str] = {}

    def get_page_id(url: str) -> str:
        if url not in page_ids:
            page_ids[url] = f"P{len(page_ids) + 1}"
        return page_ids[url]

    def get_faq_id(q: str) -> str:
        if q not in faq_ids:
            faq_ids[q] = f"F{len(faq_ids) + 1}"
        return faq_ids[q]

    def get_prod_id(p: str) -> str:
        if p not in prod_ids:
            prod_ids[p] = f"PR{len(prod_ids) + 1}"
        return prod_ids[p]

    def page_label(url: str) -> str:
        try:
            path = urlparse(url).path or "/"
        except Exception:
            path = url
        # show only path for readability
        return path

    lines = ["flowchart TD"]

    # Nodes with labels truncated and HTML-escaped for Mermaid
    def lbl(s: str, maxlen: int = 60) -> str:
        s = str(s)
        s = s.replace("\n", " ")
        s = html.escape(s).replace('"', "&quot;")
        return s if len(s) <= maxlen else s[: maxlen - 1] + "…"

    # Build nodes and edges
    edge_set = set()
    for r in rows:
        url = (r.get("url") or "").strip()
        q = (r.get("q") or "").strip()
        pr = (r.get("product") or "").strip()
        if not url:
            continue
        pid = get_page_id(url)
        # declare page node
        lines.append(f'  {pid}["Page<br/>{lbl(page_label(url), 64)}"]')
        if q:
            fid = get_faq_id(q)
            lines.append(f'  {fid}(("FAQ<br/>{lbl(q, 64)}"))')
            e = f"{pid}-->|HAS_FAQ|{fid}"
            if e not in edge_set:
                lines.append(f"  {e}")
                edge_set.add(e)
        if pr:
            prid = get_prod_id(pr)
            lines.append(f'  {prid}["Product<br/>{lbl(pr, 48)}"]')
            e2 = f"{pid}-->|MENTIONS|{prid}"
            if e2 not in edge_set:
                lines.append(f"  {e2}")
                edge_set.add(e2)
    return "\n".join(lines)


def main(out_path: str = "docs/faq_graph.md", limit: int = 200, mmd_out: str | None = "docs/faq_graph.mmd") -> None:
    rows = fetch_triplets(limit=limit)
    mermaid = to_mermaid(rows)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if mmd_out:
        os.makedirs(os.path.dirname(mmd_out), exist_ok=True)
        with open(mmd_out, "w", encoding="utf-8") as mf:
            mf.write(mermaid)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("## Page–FAQ–Product overview\n\n")
        f.write(
            "This diagram shows how FAQs are attached to Pages and how Pages anchor Products.\n\n"
        )
        f.write("```mermaid\n")
        f.write(mermaid)
        f.write("\n```\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/faq_graph.md")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--mmd-out", default="docs/faq_graph.mmd")
    args = parser.parse_args()
    main(out_path=args.out, limit=args.limit, mmd_out=args.mmd_out)
