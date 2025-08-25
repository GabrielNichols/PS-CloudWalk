from __future__ import annotations

from typing import List, Dict, Any
import json
import re
import unicodedata

from neo4j import GraphDatabase, Driver
from langchain_core.documents import Document

from app.settings import settings


def _get_driver() -> Driver:
    if not settings.neo4j_username or not settings.neo4j_password:
        raise RuntimeError("Neo4j credentials not configured")
    uri = settings.neo4j_uri or (
        f"neo4j+s://{settings.aura_instanceid}.databases.neo4j.io"
        if settings.aura_instanceid
        else None
    )
    if not uri:
        raise RuntimeError("Neo4j URI not configured")
    return GraphDatabase.driver(uri, auth=(settings.neo4j_username, settings.neo4j_password))


def ensure_constraints() -> None:
    # Drop legacy unique constraints on `name` to allow multiple display variants while merging by canonical_name
    drop_statements = [
        "CALL db.constraints() YIELD name, description WHERE description CONTAINS 'Product' AND description CONTAINS 'name' CALL { WITH name CALL db.dropConstraint(name) YIELD name AS dn RETURN dn } IN TRANSACTIONS RETURN 1",
        "CALL db.constraints() YIELD name, description WHERE description CONTAINS 'Feature' AND description CONTAINS 'name' CALL { WITH name CALL db.dropConstraint(name) YIELD name AS dn RETURN dn } IN TRANSACTIONS RETURN 1",
        "CALL db.constraints() YIELD name, description WHERE description CONTAINS 'Fee' AND description CONTAINS 'name' CALL { WITH name CALL db.dropConstraint(name) YIELD name AS dn RETURN dn } IN TRANSACTIONS RETURN 1",
        "CALL db.constraints() YIELD name, description WHERE description CONTAINS 'HowTo' AND description CONTAINS 'name' CALL { WITH name CALL db.dropConstraint(name) YIELD name AS dn RETURN dn } IN TRANSACTIONS RETURN 1",
    ]
    cypher_statements = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Feature) REQUIRE f.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Fee) REQUIRE f.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (h:HowTo) REQUIRE h.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (pg:Page) REQUIRE pg.url IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
        # Recreate entityIdx to include both name and canonical_name for better recall
        "DROP INDEX entityIdx IF EXISTS",
        "CREATE FULLTEXT INDEX entityIdx IF NOT EXISTS FOR (n:Product|Feature|Fee|HowTo) ON EACH [n.name, n.canonical_name]",
        # FAQ: unique by question; fulltext over question+answer
        "CREATE CONSTRAINT IF NOT EXISTS FOR (fq:FAQ) REQUIRE fq.question IS UNIQUE",
        "CREATE FULLTEXT INDEX faqIdx IF NOT EXISTS FOR (fq:FAQ) ON EACH [fq.question, fq.answer]",
        # Canonical unique keys for deduplication across case/accents/punctuation
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.canonical_name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Feature) REQUIRE f.canonical_name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Fee) REQUIRE f.canonical_name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (h:HowTo) REQUIRE h.canonical_name IS UNIQUE",
    ]
    driver = _get_driver()
    db = settings.neo4j_database or "neo4j"
    with driver.session(database=db) as session:
        # Best-effort drops (ignore errors)
        for stmt in drop_statements:
            try:
                session.run(stmt).consume()
            except Exception:
                pass
        for stmt in cypher_statements:
            session.run(stmt).consume()
    driver.close()


KG_TYPES = {"Product", "Feature", "Fee", "HowTo"}


NOISE_TERMS = {
    "logo",
    "bandeira",
    "imagem",
    "baixar",
    "download",
    "informações úteis",
    "sobre",
    "termos",
    "política",
}

PRODUCT_ALLOWLIST = {
    "maquininha",
    "tap to pay",
    "maquininha celular",
    "pdv",
    "receba na hora",
    "gestão de cobrança",
    "link de pagamento",
    "loja online",
    "boleto",
    "conta digital",
    "pix",
    "pix parcelado",
    "empréstimo",
    "cartão",
    "rendimento",
}


def _normalize(s: str) -> str:
    value = (s or "").strip()
    # remove obvious noise prefixes
    lowered = value.lower()
    for t in NOISE_TERMS:
        if lowered.startswith(t + " "):
            value = value[len(t) + 1 :]
            break
    return value.strip()


def _canonicalize(s: str) -> str:
    """Case/diacritics/punctuation-insensitive canonical key.

    Example: "Cartão Virtual Inteligente" -> "cartao virtual inteligente"
    """
    if not s:
        return ""
    # Normalize diacritics
    nfkd = unicodedata.normalize("NFKD", s)
    no_accents = "".join([c for c in nfkd if not unicodedata.combining(c)])
    # Lowercase and remove non-alphanumeric except spaces
    lowered = no_accents.lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    # Collapse spaces
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_noise_entity(text: str) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered or len(lowered) < 3:
        return True
    if any(t in lowered for t in NOISE_TERMS):
        # keep card brands only if explicitly mentioned as accepted brand
        if "hipercard" in lowered and "logo" not in lowered:
            return False
        return True
    return False


def _extract_triples_with_openai(
    docs: List[Document], per_doc_limit: int = 5
) -> List[Dict[str, Any]]:
    # Light-weight JSON extraction using OpenAI Chat
    from openai import OpenAI  # lazy import

    client = OpenAI(api_key=settings.openai_api_key)
    triples: List[Dict[str, Any]] = []
    for d in docs:
        content = d.page_content[:6000]
        url = (d.metadata or {}).get("url") or (d.metadata or {}).get("source")
        prompt = (
            "You are an information extractor. Produce a STRICT JSON array of knowledge triples for a payments product graph. "
            "Use only these types: Product, Feature, Fee, HowTo. Allowed predicates: HAS_FEATURE, HAS_FEE, HAS_HOWTO. "
            "Ignore analytics/UI/boilerplate terms (logo, banner, download, newsletter, utm, referrer, badge). "
            "Prefer concrete product facts (e.g., 'Maquininha Smart HAS_FEE crédito 12x 8,99%'). "
            f"Return at most {per_doc_limit} triples. Each: {{subject, subject_type, predicate, object, object_type}}. "
            "If unsure, skip.\n\nText:\n" + content
        )
        completion = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        raw = completion.choices[0].message.content or "[]"
        # try parse JSON array from the response
        start = raw.find("[")
        end = raw.rfind("]")
        payload = raw[start : end + 1] if start >= 0 and end >= 0 else "[]"
        try:
            data = json.loads(payload)
            for t in data:
                subj_type = str(t.get("subject_type", "")).strip()
                obj_type = str(t.get("object_type", "")).strip()
                pred = str(t.get("predicate", "")).strip().upper()
                if subj_type not in KG_TYPES and subj_type:
                    continue
                if obj_type not in KG_TYPES and obj_type:
                    continue
                subj = _normalize(str(t.get("subject", "")))
                obj = _normalize(str(t.get("object", "")))
                if _is_noise_entity(subj) or _is_noise_entity(obj):
                    continue
                # weak product typing if text matches allowlist
                if not subj_type:
                    if any(k in subj.lower() for k in PRODUCT_ALLOWLIST):
                        subj_type = "Product"
                    else:
                        subj_type = "Feature"
                if not obj_type:
                    if any(k in obj.lower() for k in PRODUCT_ALLOWLIST):
                        obj_type = "Product"
                    else:
                        obj_type = "Feature"
                if pred not in {"HAS_FEATURE", "HAS_FEE", "HAS_HOWTO"}:
                    continue
                triples.append(
                    {
                        "subject": subj,
                        "subject_type": subj_type,
                        "predicate": pred,
                        "object": obj,
                        "object_type": obj_type,
                        "page_url": url,
                    }
                )
        except Exception:
            continue
    return triples


def _persist_triples(triples: List[Dict[str, Any]]) -> None:
    if not triples:
        return
    driver = _get_driver()
    db = settings.neo4j_database or "neo4j"
    with driver.session(database=db) as session:
        for t in triples:
            subj_disp = _normalize(str(t.get("subject", "")))
            obj_disp = _normalize(str(t.get("object", "")))
            subj_can = _canonicalize(subj_disp)
            obj_can = _canonicalize(obj_disp)
            if not subj_can or not obj_can:
                continue
            cy = f"""
            MERGE (pg:Page {{url: $page_url}})
            MERGE (s:`{t['subject_type']}` {{canonical_name: $s_can}})
              ON CREATE SET s.name = $s_name
            MERGE (o:`{t['object_type']}` {{canonical_name: $o_can}})
              ON CREATE SET o.name = $o_name
            MERGE (s)-[r:{t['predicate']}]->(o)
            MERGE (pg)-[:MENTIONS]->(s)
            MERGE (pg)-[:MENTIONS]->(o)
            MERGE (s)-[:DESCRIBED_ON]->(pg)
            MERGE (o)-[:DESCRIBED_ON]->(pg)
            RETURN 1
            """
            session.run(
                cy,
                page_url=t.get("page_url"),
                s_can=subj_can,
                s_name=subj_disp,
                o_can=obj_can,
                o_name=obj_disp,
            ).consume()
    driver.close()


def build_and_persist_kg(
    documents: List[Document], per_doc_limit: int = 5, max_docs: int | None = None
) -> None:
    ensure_constraints()
    if max_docs is not None:
        documents = documents[:max_docs]
    if not settings.openai_api_key:
        return
    triples = _extract_triples_with_openai(documents, per_doc_limit=per_doc_limit)
    _persist_triples(triples)


def persist_faqs(faq_items: List[Dict[str, Any]]) -> None:
    """Persist FAQ items: (Page)-[:HAS_FAQ]->(FAQ) and (Product)-[:HAS_FAQ]->(FAQ) when product is known.

    Each item: {question, answer, url, product?}
    """
    if not faq_items:
        return
    # Precompute canonical product names to align with graph constraints
    rows: List[Dict[str, Any]] = []
    for it in faq_items:
        prod = it.get("product")
        prod_can = _canonicalize(prod) if prod else ""
        rows.append(
            {
                "question": it.get("question"),
                "answer": it.get("answer"),
                "url": it.get("url"),
                "product": prod,
                "prod_can": prod_can,
            }
        )

    driver = _get_driver()
    db = settings.neo4j_database or "neo4j"
    cypher = (
        "UNWIND $rows AS row "
        "MERGE (fq:FAQ {question: row.question}) "
        "SET fq.answer = row.answer "
        "WITH row, fq "
        "MERGE (pg:Page {url: row.url}) "
        "MERGE (pg)-[:HAS_FAQ]->(fq) "
        "WITH row, fq "
        "FOREACH(_ IN CASE WHEN row.product IS NOT NULL AND row.prod_can IS NOT NULL AND row.prod_can <> '' THEN [1] ELSE [] END | "
        "  MERGE (p:Product {canonical_name: row.prod_can}) ON CREATE SET p.name = row.product "
        "  MERGE (p)-[:HAS_FAQ]->(fq) "
        "  MERGE (p)-[:DESCRIBED_ON]->(pg) "
        ") "
        "RETURN count(fq) as upserts"
    )
    with driver.session(database=db) as s:
        s.run(cypher, rows=rows).consume()
    driver.close()
