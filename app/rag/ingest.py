from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from app.rag.embeddings import get_embeddings
from app.rag.vectorstore_milvus import MilvusVectorStore
from app.settings import settings
import os

from trafilatura import fetch_url, extract
import re


URL_TAGS = {
    "/cartao": "cartao cartão card virtual cashback anuidade zero taxas do cartão",
    "/maquininha-celular": "tap to pay maquininha celular infinite tap nfc",
    "/maquininha": "maquininha smart máquina cartão taxas maquininha",
    "/pix": "pix pagamentos taxa zero",
    "/rendimento": "rendimento ganhos juros yield interest",
    "/pdv": "pdv ponto de venda gestão estoque",
    "/conta-digital": "conta digital conta pj banco pagamentos",
    "/gestao-de-cobranca": "gestão de cobrança cobranças boletos links",
    "/gestao-de-cobranca-2": "gestão de cobrança cobranças boletos links",
    "/link-de-pagamento": "link de pagamento venda a distância",
    "/loja-online": "loja online ecommerce catálogo",
    "/boleto": "boleto cobrança",
    "/emprestimo": "empréstimo crédito capital de giro",
}


def _tags_for_url(url: str) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlparse

        path = urlparse(url).path or "/"
    except Exception:
        path = url
    # longest match wins
    best = ""
    for frag, tags in URL_TAGS.items():
        if frag and frag in path:
            best = tags
            break
    return best


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

    # 3) Embeddings + Vector index
    emb = get_embeddings()
    if emb:
        prepared = []
        faq_rows: list[dict] = []
        for d in splits:
            meta = d.metadata or {}
            if "source" in meta and not meta.get("url"):
                meta["url"] = meta.get("source")
            url_val = str(meta.get("url") or "")
            tags = _tags_for_url(url_val)
            prefix = f"URL: {url_val}\nTAGS: {tags}\n\n"
            prepared.append(Document(page_content=prefix + d.page_content, metadata=meta))
            # FAQ extractor v2: capture contiguous blocks under FAQ heading until next heading
            content = d.page_content
            cl = content.lower() if content else ""
            if content and ("\nfaq\n" in cl or "perguntas frequentes" in cl):
                lines = [ln.rstrip() for ln in content.splitlines()]
                # find indices of questions (lines ending with '?') and stitch answers until next question or blank line gap
                i = 0
                while i < len(lines):
                    qline = lines[i].strip()
                    if qline.endswith("?") and len(qline) > 8:
                        # accumulate answer lines until stop condition
                        j = i + 1
                        answer_lines: list[str] = []
                        while j < len(lines):
                            cur = lines[j].strip()
                            if cur.endswith("?") and len(cur) > 8:
                                break
                            if cur.startswith("#") or cur.lower().startswith("faq"):
                                break
                            if cur == "" and answer_lines and answer_lines[-1] == "":
                                # two consecutive blanks -> likely section break
                                break
                            answer_lines.append(cur)
                            j += 1
                        ans = " ".join([ln for ln in answer_lines if ln]).strip()
                        q = re.sub(r"\s+", " ", qline)
                        if len(ans) > 10:
                            faq_rows.append(
                                {
                                    "question": q[:512],
                                    "answer": ans[:1600],
                                    "url": url_val,
                                    "product": "Cartão Virtual Inteligente" if "/cartao" in url_val else "InfinitePay",
                                }
                            )
                        i = j
                        continue
                    i += 1
        # Index in batches to respect API/token limits
        MilvusVectorStore.index_in_batches(prepared, embedding=emb, batch_size=batch_size)
        # 4) Index FAQ documents separately (Milvus only supports vector indexing)
        if faq_rows:
            faq_docs = [
                Document(
                    page_content=f"Q: {row['question']}\nA: {row['answer']}",
                    metadata={"url": row["url"], "kind": "faq", "product": row.get("product")},
                )
                for row in faq_rows
            ]
            MilvusVectorStore.index_faqs_in_batches(faq_docs, embedding=emb, batch_size=64)


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
