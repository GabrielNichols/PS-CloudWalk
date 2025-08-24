# README — Agent Swarm (LangGraph + Graph-RAG on Neo4j)

> Multi-agent orchestrated with LangGraph, **Graph-RAG (KG + vector)** over **Neo4j AuraDB Free**, HTTP API via **FastAPI**, deploy **Vercel Functions (Python/ASGI)**, **Docker** for local dev & tests. Uses **OpenAI** for LLM + embeddings.

Note: This repository is being implemented. Initial scaffolding, API, LangGraph state/builder, and agent skeletons are included. Full RAG, tools, and tests will be completed next.

## ✨ Highlights

* **Swarm de 3+ agentes**: `RouterAgent`, `KnowledgeAgent` (Graph-RAG + WebSearch), `CustomerSupportAgent` (com **2+ tools**), `Personality` (pós-processamento).
* **RAG híbrido**: **vector (Neo4jVector)** + **Graph/Cypher** (KG) com *query routing* (LangGraph **conditional edges/handoffs**). ([python.langchain.com][2], [langchain-ai.github.io][1])
* **Ingestão** das páginas da **InfinitePay** (fornecidas no desafio) via `AsyncHtmlLoader`, *chunking* e *embeddings* locais (HuggingFace) ou API. ([python.langchain.com][7])
* **Deploy gratuito**: **Vercel Functions (Python/ASGI)** para API; **Neo4j AuraDB Free** como banco gerenciado. ([Vercel][14], [Graph Database & Analytics][9])
* **Testes**: unit (agentes, RAG, roteamento & personality) + e2e (API).
* **Docker**: desenvolvimento local (Uvicorn + Neo4j + seed). ([FastAPI][11])
* **Bônus**: *Guardrails* simples + *Human redirect* + 4º agente opcional.

---

## 🧭 Arquitetura

```mermaid
flowchart LR
  In((Input)) --> R[Router Agent]
  R -- knowledge --> K[Knowledge Agent]
  R -- support --> S[Customer Support Agent]
  R -. custom .-> C[Your Custom Agent (optional)]
  K --->|RAG: Vector+KG| Neo[(Neo4j AuraDB)]
  S -->|tools| T1[(User Profile Store)]
  S -->|tools| T2[(Ticketing/Case Tool)]
  K --> P[Personality Layer]
  S --> P
  C --> P
  P --> Out((Output))
```

**Padrões LangGraph** (nós = funções/agents, arestas = fluxo; *conditional edges/handoffs* entre agentes; *checkpointer* para memória e *threads*). ([langchain-ai.github.io][15])

---

## 🗂️ Estrutura do repositório

```
.
├── app/
│   ├── api/
│   │   └── main.py                 # FastAPI (ASGI) — expõe /api/v1/message
│   ├── graph/
│   │   ├── state.py                # Pydantic State + tipagem
│   │   ├── builder.py              # monta StateGraph (LangGraph)
│   │   └── memory.py               # checkpointer/memory
│   ├── agents/
│   │   ├── base.py                 # ABC + contrato de Agent
│   │   ├── router.py               # RouterAgent (LLM + regras)
│   │   ├── knowledge.py            # KnowledgeAgent (Graph-RAG)
│   │   ├── support.py              # CustomerSupportAgent (tools)
│   │   └── personality.py          # Personality (style/locale/safety)
│   ├── rag/
│   │   ├── ingest.py               # coleta páginas InfinitePay (async)
│   │   ├── splitter.py             # chunking/config
│   │   ├── embeddings.py           # HF/OpenAI embeddings
│   │   ├── vectorstore.py          # Neo4jVector (indexação/busca)
│   │   └── graph_kg.py             # LLMGraphTransformer -> KG (Cypher)
│   ├── tools/
│   │   ├── web_search.py           # Tavily (LangChain Tool)
│   │   ├── user_profile.py         # Tool #1 - perfil do cliente
│   │   └── ticketing.py            # Tool #2 - criar/consultar ticket
│   └── settings.py                 # config .env (pydantic-settings)
├── tests/
│   ├── unit/
│   │   ├── test_router.py
│   │   ├── test_knowledge.py
│   │   ├── test_support.py
│   │   └── test_personality.py
│   └── e2e/
│       └── test_api.py
├── docker/
│   ├── Dockerfile                  # app (local/CI)
│   └── docker-compose.yml          # app + neo4j local
├── vercel.json                     # roteia /api para Python runtime
├── requirements.txt                # deps
├── .env.example
└── README.md
```

---

## ⚙️ Configuração

Crie `.env` (baseado em `env.example` — se preferir, copie para `.env` localmente):

```ini
# LLM / embeddings (OpenAI)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small
EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2  # fallback opcional

# Web search (opcional)
TAVILY_API_KEY=

# Neo4j (AuraDB Free recomendado)
NEO4J_URI=neo4j+s://<your-instance>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=********
NEO4J_DATABASE=neo4j
```

> **Por que AuraDB Free?** É um **tier gratuito** gerenciado, ideal pra POCs e desafios. ([Graph Database & Analytics][9])

---

## 📥 Ingestão (corpus InfinitePay)

1. **Coleta**: `AsyncHtmlLoader` paraleliza o *fetch* dos URLs do desafio; `BeautifulSoup` sanitiza; `RecursiveCharacterTextSplitter` faz *chunking*. ([python.langchain.com][7])
2. **Embeddings**: HF local (default) ou API.
3. **Vector Store**: `Neo4jVector` cria índice ANN (cosine/euclidean) e suporta *hybrid search*. ([python.langchain.com][2])
4. **Knowledge Graph (KG)**: `LLMGraphTransformer` extrai entidades/relacionamentos (Pages→Products→Features) e persiste no Neo4j (Cypher). ([python.langchain.com][16])

```bash
# 1) instalar deps
pip install -r requirements.txt

# 2) rodar ingestão
python -m app.rag.ingest --urls-file data/infinitepay_urls.txt
```

---

## 🧠 RAG (Vector + Graph)

* **Retriever híbrido**:

  * *Vector*: top-k por similaridade (Neo4jVector)
  * *Graph*: Cypher focado em **Products/Features/Fees/How-tos**, navegando vizinhanças no KG
  * **Router (LangGraph)** decide *vector*, *graph* ou **ambos** conforme intenção/entidade (conditional edges). ([python.langchain.com][2], [langchain-ai.github.io][1])

> Padrão **Graph-RAG**: combina relações do KG com semântica do vetor para *grounding* melhor e rastreável. ([LangChain Blog][5], [Graph Database & Analytics][6])

---

## 👥 Agentes

### 1) `RouterAgent`

* Classifica intenção: **knowledge**, **support**, **chitchat/out-of-scope**.
* `LangGraph` **conditional edges** para despachar fluxo. ([langchain-ai.github.io][1])

### 2) `KnowledgeAgent`

* **RAG híbrido** (vector + KG) sobre Neo4j.
* *Fallback* para **WebSearch Tool (Tavily)** em perguntas gerais/externas. ([langchain-ai.github.io][12])

### 3) `CustomerSupportAgent`

* Usa **2 tools** mínimas:

  * `user_profile`: obtém dados simulados do cliente (ex.: status da conta, limites, KYC).
  * `ticketing`: abre/consulta **ticket** (simulação local em SQLite/JSON).
* Fluxo segue para `Personality`.

### 4) (Bônus) `PricingAgent` *(opcional)*

* Especializado em **taxas/tarifas** por produto (Maquininha, Tap to Pay, etc.), consolidando regras do corpus.

### `Personality`

* Camada final (tom/idioma/estilo; *hedging* + *guardrails* simples e **redirect-to-human** quando necessário).

---

## 🧵 Memória e Observabilidade

* **Checkpointer** (LangGraph) por `thread_id` para continuidade, *time-travel*, *human-in-the-loop*. ([langchain-ai.github.io][17])
* Logs estruturados + IDs de *run/thread* nos headers da API.

---

## 🛠️ HTTP API

```
POST /api/v1/message
Content-Type: application/json

{
  "message": "What are the fees of the Maquininha Smart?",
  "user_id": "client789",
  "locale": "en"  // opcional: "pt-BR" autodetect
}
```

**Resposta (exemplo):**

```json
{
  "ok": true,
  "agent": "KnowledgeAgent",
  "answer": "For Maquininha Smart, ...",
  "grounding": {
    "mode": "graph+vector",
    "sources": [
      {"url": "https://www.infinitepay.io/maquininha", "type": "page"},
      {"node": "Product:MaquininhaSmart", "type": "kg"}
    ]
  },
  "meta": {"thread_id": "client789", "latency_ms": 812}
}
```

---

## ▶️ Rodando localmente (Docker)

```bash
# 1) Neo4j + app
docker compose -f docker/docker-compose.yml up --build

# 2) Ingest (em outro terminal)
docker exec -it agent-swarm-app python -m app.rag.ingest --urls-file /app/data/infinitepay_urls.txt
```

> O **Dockerfile** segue a recomendação oficial de FastAPI + Uvicorn (camadas slim, non-root). ([FastAPI][11])

---

## ☁️ Deploy gratuito (Vercel)

> A Vercel **não executa imagens Docker** diretamente; use **Vercel Functions**. Basta expor um **app ASGI** (FastAPI) em `api/index.py` e declarar deps em `requirements.txt`. ([Vercel][10])

**Passos:**

1. Suba o repositório no GitHub.
2. Na Vercel, “New Project” → importe o repo.
3. **Python Runtime**: o arquivo `api/index.py` deve expor `app` (ASGI).
4. Em **Settings → Environment Variables**, adicione as variáveis do `.env`.
5. Deploy (CLI opcional: `vercel --prod`). ([Vercel][18])

**Exemplo mínimo de `api/index.py` (já incluso no repo):**

```python
# api/index.py
from app.api.main import app  # FastAPI instance -> ASGI for Vercel
# Vercel detecta "app" automaticamente (WSGI/ASGI).
```

---

## 🧪 Testes

* **Unitários**:

  * `test_router.py`: roteamento por intenção (inclui casos limítrofes/“out-of-scope”).
  * `test_knowledge.py`: *retriever* (vector/graph), *query routing*, *grounding*.
  * `test_support.py`: ferramentas (perfil, ticket).
  * `test_personality.py`: tom/idioma, *safety/guardrails*.
* **E2E**:

  * `test_api.py` (FastAPI `TestClient`): cenários fornecidos no enunciado.
* Rodar:

```bash
pytest -q
```

---

## 📝 Estratégia de Testes (resumo)

* **Unit**: *stubs* para LLM/embeddings (fixando *seed*) + Neo4j container efêmero com fixture.
* **Integration**: suíte que cobre ingestão→indexação→consulta (marcada `@slow`).
* **E2E**: valida contrato JSON, *agent attribution*, *grounding* e *localization*.

> A FastAPI fornece caminho “feliz” para testes assíncronos/ASGI; combinamos com `pytest`/`TestClient`. ([FastAPI][19])

---

## 🧩 Detalhes de Implementação

### LangGraph (StateGraph)

* **State** (Pydantic): `{ user_id, locale, message, intent, retrieval, answer, trace }`.
* **Edges**: `START → Router → {Knowledge|Support|Custom} → Personality → END` (**conditional edges**). ([langchain-ai.github.io][1])
* **Checkpointer**: `thread_id = user_id` por padrão. ([langchain-ai.github.io][17])

### RAG em Neo4j

* **Vector**: `Neo4jVector` (ANN; cosine/euclidean; híbrido) para *chunks*. ([python.langchain.com][2])
* **KG**: `LLMGraphTransformer` para entidades/relacionamentos → *prompted Cypher*. ([python.langchain.com][16])
* **Routing**: se pergunta for *rates/fees/how-to/product*, prioriza **Graph + Vector**; para open-domain, chama **WebSearch (Tavily)** como *tool*. ([langchain-ai.github.io][12])

### Customer Support — Tools (exemplos)

* `user_profile.get_user_info(user_id)` → {status, saldo, limites, bloqueios}.
* `ticketing.open_ticket(user_id, category, summary)` / `get_ticket(id)`.

---

## 🔐 Guardrails & Handoff

* **Guardrails leves**: filtro de PII & *prompt-injection*, *rate limiting* por `user_id`, *blocked topics*.
* **Redirect to human**: se `intent=support` + `confidence<τ` → criar ticket e encerrar com instrução humana.

---

## 🗃️ Requisitos

* Python 3.12
* Neo4j AuraDB Free (ou Neo4j local via Docker) ([Graph Database & Analytics][9])
* Vercel account (Hobby) com **Python Runtime**. ([Vercel][14])

---

## 🔗 Como eu usei LLM tools aqui

* **LangGraph** para orquestrar multi-agentes (roteamento, handoffs, memória). ([langchain-ai.github.io][1])
* **LangChain** integra **Neo4jVector** + **LLMGraphTransformer** e carrega docs via `AsyncHtmlLoader`. ([python.langchain.com][2])
* **Tavily** como *tool* de busca web atual. ([langchain-ai.github.io][12])

---

## 🧪 Cenários (do enunciado) cobertos

* *Fees/Cost* (Maquininha Smart) → `PricingAgent`/**KnowledgeAgent** (Graph-RAG).
* *Rates* débito/crédito → **KnowledgeAgent** (KG + vector).
* *Tap to Pay (celular como maquininha)* → **KnowledgeAgent** (how-to).
* Notícias/Esportes (fora do corpus) → **WebSearch Tool** (Tavily) + resposta desambiguada.
* “Não consigo transferir / logar” → **Support** + tools (`user_profile`, `ticketing`) + **redirect-to-human** se preciso.

---

## 📄 Licença

MIT

---

# Snippets úteis (já prontos no repo)

### 1) `graph/builder.py` (esqueleto)

```python
from langgraph.graph import StateGraph, END
from app.graph.state import AppState
from app.agents.router import router_node, route_decision
from app.agents.knowledge import knowledge_node
from app.agents.support import support_node
from app.agents.personality import personality_node

def build_graph(checkpointer=None):
    g = StateGraph(AppState)
    g.add_node("router", router_node)
    g.add_node("knowledge", knowledge_node)
    g.add_node("support", support_node)
    g.add_node("personality", personality_node)

    g.add_edge("knowledge", "personality")
    g.add_edge("support", "personality")
    g.add_edge("personality", END)

    g.add_edge("router", "knowledge")  # default
    g.add_conditional_edges("router", route_decision, {  # conditional edges
        "knowledge": "knowledge",
        "support": "support",
        "end": END
    })

    g.set_entry_point("router")
    return g.compile(checkpointer=checkpointer)
```

> *Nodes/edges/conditional edges* são padrões idiomáticos de LangGraph para multi-agentes. ([langchain-ai.github.io][15])

### 2) `rag/ingest.py` (miolo da ingestão)

```python
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.rag.embeddings import get_embeddings
from app.rag.vectorstore import Neo4jVectorStore

loader = AsyncHtmlLoader(urls, max_concurrency=8)  # coleta
docs = loader.load()
splits = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150).split_documents(docs)
emb = get_embeddings()  # HF por padrão
Neo4jVectorStore.from_documents(splits, embedding=emb)  # cria índice ANN
```

> `AsyncHtmlLoader` & `Neo4jVector` documentados oficialmente. ([python.langchain.com][7])

### 3) `tools/web_search.py` (Tavily)

```python
from langchain_tavily import TavilySearchResults
tavily = TavilySearchResults(k=5)
```

> Tutorial oficial de “Add tools” com Tavily em LangGraph. ([langchain-ai.github.io][12])

---

[1]: https://langchain-ai.github.io/langgraph/concepts/multi_agent/?utm_source=chatgpt.com "LangGraph Multi-Agent Systems - Overview"
[2]: https://python.langchain.com/docs/integrations/vectorstores/neo4jvector/?utm_source=chatgpt.com "Neo4j Vector Index"
[3]: https://js.langchain.com/docs/integrations/vectorstores/neo4jvector/?utm_source=chatgpt.com "Neo4j Vector Index"
[4]: https://neo4j.com/labs/genai-ecosystem/langchain/?utm_source=chatgpt.com "LangChain Neo4j Integration - Neo4j Labs"
[5]: https://blog.langchain.com/enhancing-rag-based-applications-accuracy-by-constructing-and-leveraging-knowledge-graphs/?utm_source=chatgpt.com "Enhancing RAG-based application accuracy by ..."
[6]: https://neo4j.com/blog/developer/neo4j-graphrag-workflow-langchain-langgraph/?utm_source=chatgpt.com "Create a Neo4j GraphRAG Workflow Using LangChain ..."
[7]: https://python.langchain.com/docs/integrations/document_loaders/async_html/?utm_source=chatgpt.com "AsyncHtml | 🦜️🔗 LangChain"
[8]: https://api.python.langchain.com/en/latest/document_loaders/langchain_community.document_loaders.async_html.AsyncHtmlLoader.html?utm_source=chatgpt.com "langchain_community.document_loaders.async_html."
[9]: https://neo4j.com/product/auradb/?utm_source=chatgpt.com "Neo4j AuraDB: Fully Managed Graph Database"
[10]: https://vercel.com/guides/does-vercel-support-docker-deployments?utm_source=chatgpt.com "Does Vercel support Docker deployments?"
[11]: https://fastapi.tiangolo.com/deployment/docker/?utm_source=chatgpt.com "FastAPI in Containers - Docker"
[12]: https://langchain-ai.github.io/langgraph/tutorials/get-started/2-add-tools/?utm_source=chatgpt.com "2. Add tools - GitHub Pages"
[13]: https://python.langchain.com/docs/integrations/tools/tavily_search/?utm_source=chatgpt.com "Tavily Search | 🦜️🔗 LangChain"
[14]: https://vercel.com/docs/functions/runtimes/python "Using the Python Runtime with Vercel Functions"
[15]: https://langchain-ai.github.io/langgraph/concepts/low_level/?utm_source=chatgpt.com "state graph node - GitHub Pages"
[16]: https://python.langchain.com/docs/how_to/graph_constructing/?utm_source=chatgpt.com "How to construct knowledge graphs"
[17]: https://langchain-ai.github.io/langgraph/concepts/persistence/?utm_source=chatgpt.com "LangGraph persistence - GitHub Pages"
[18]: https://vercel.com/docs/deployments?utm_source=chatgpt.com "Deploying to Vercel"
[19]: https://fastapi.tiangolo.com/deployment/?utm_source=chatgpt.com "Deployment - FastAPI"
