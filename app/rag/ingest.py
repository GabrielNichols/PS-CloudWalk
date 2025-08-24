from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from app.rag.embeddings import get_embeddings
from app.rag.vectorstore import Neo4jVectorStore
from app.rag.graph_kg import build_and_persist_kg
from app.settings import settings
import os

from trafilatura import fetch_url, extract


def _extract_with_trafilatura(urls: list[str]) -> list[Document]:
    docs: list[Document] = []
    for url in urls:
        downloaded = fetch_url(url)
        if not downloaded:
            continue
        # Extract clean text (no navigation/menus/utm or boilerplate)
        text = extract(downloaded, include_links=False, include_images=False, favor_precision=True)
        if not text:
            continue
        docs.append(Document(page_content=text, metadata={"url": url}))
    return docs


def _extract_with_crawl_fallback(urls: list[str]) -> list[Document]:
    # Ensure a reasonable default UA to avoid provider blocks
    os.environ.setdefault(
        "USER_AGENT",
        "Mozilla/5.0 (compatible; PS-CloudWalk/1.0; +https://cloudwalk.ai)",
    )
    loader = AsyncHtmlLoader(urls)
    return loader.load()


def ingest(urls: list[str], batch_size: int = 80) -> None:
    # 1) Extract content (Firecrawl preferred)
    raw_docs: list[Document] = []
    # Prefer precise content extraction
    raw_docs = _extract_with_trafilatura(urls)
    if not raw_docs:
        raw_docs = _extract_with_crawl_fallback(urls)

    # 2) Chunking
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800, chunk_overlap=120, separators=["\n## ", "\n# ", "\n\n", "\n", " "]
    )
    splits = splitter.split_documents(raw_docs)

    # 3) Embeddings + Vector index on Neo4j
    emb = get_embeddings()
    if emb:
        prepared = []
        for d in splits:
            meta = d.metadata or {}
            if "source" in meta and not meta.get("url"):
                meta["url"] = meta.get("source")
            prepared.append(Document(page_content=d.page_content, metadata=meta))
        # Index in batches to respect API/token limits
        Neo4jVectorStore.index_in_batches(prepared, embedding=emb, batch_size=batch_size)
        # 4) Build KG (entities/relations) with OpenAI and persist with MERGE (idempotent)
        build_and_persist_kg(prepared, per_doc_limit=5, max_docs=200)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--urls-file", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=80)
    args = parser.parse_args()
    with open(args.urls_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    if args.limit:
        urls = urls[: args.limit]
    # Ensure UA for fetchers
    os.environ.setdefault(
        "USER_AGENT",
        "Mozilla/5.0 (compatible; PS-CloudWalk/1.0; +https://cloudwalk.ai)",
    )
    ingest(urls, batch_size=args.batch_size)
