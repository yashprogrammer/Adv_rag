<div align="center">

# 🔮 ADV RAG

### *E-commerce Customer Support Copilot — Text2SQL + Core RAG + Caching + LLM Security*

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.6-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-DC244C?logo=qdrant)](https://qdrant.tech)
[![Postgres](https://img.shields.io/badge/Postgres-16-4169E1?logo=postgresql)](https://www.postgresql.org)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?logo=openai)](https://openai.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-1C3C3C?logo=langchain)](https://langchain.com/langgraph)
[![Upstash](https://img.shields.io/badge/Upstash-Redis-00E9A3?logo=upstash)](https://upstash.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

<p align="center">
  <i>🛡️ 9 Security Layers • ⚡ 5-Tier Cache • 🗄️ Text2SQL + RAG • 🤖 Human-in-the-Loop</i>
</p>

[Features](#-features) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [API](#-api-endpoints) • [Security](#-security-layers) • [Caching](#-caching-topology)

<br>

```ascii
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   👤 Ask Question  →  🧠 Intent Router  →  📊 SQL | 📚 RAG   ║
║                                                              ║
║   ✅ 9 Security Layers — from input validation to output     ║
║   ✅ 5-Tier Cache — embeddings to full answers               ║
║   ✅ Human-in-the-Loop SQL Approval — safe Text2SQL          ║
║   ✅ Hybrid Search — Dense + Sparse + RRF Fusion             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🗄️ **Text2SQL + Approval**
- 🧠 **LLM-generated SQL** from natural language
- ✋ **Human-in-the-loop approval** via LangGraph interrupts
- 🔒 **SELECT-only enforcement** with keyword blocklists
- 📊 **Schema introspection** auto-loaded from Postgres

</td>
<td width="50%">

### 📚 **Core RAG Pipeline**
- 🔍 **Hybrid search** — Dense + Sparse + RRF
- 🎯 **HyDE** — hypothetical answer embeddings
- 🏆 **Cross-encoder reranking** (local / Voyage)
- 🌐 **CRAG + Tavily** web-search fallback

</td>
</tr>
<tr>
<td width="50%">

### 🛡️ **Security-First Design**
- 🔐 **9 defensive layers** from L1 (validation) to L9 (output schema)
- 🚫 **Prompt injection scanning** via llm-guard
- 🔒 **JWT auth + rate limiting + token budgets**
- 🛡️ **PII redaction** on input and output

</td>
<td width="50%">

### ⚡ **Performance & Caching**
- 💾 **5-tier cache** — intent, embeddings, SQL, results, answers
- 📦 **Doc deduplication** via S3 / local SHA-256 cache
- 🚀 **Async-first** I/O with loguru structured logging
- 🏗️ **CloudFormation + ECS** production deployment ready

</td>
</tr>
</table>

---

## 🏗️ Architecture

<div align="center">

```mermaid
graph LR
    A[📤 User Query] --> B{Intent?}
    B -->|RAG| C[🔍 Vector Search]
    B -->|SQL| D[🗄️ Text2SQL]
    B -->|Hybrid| E[🔍 + 🗄️ Combined]

    C --> F[🤖 Generate Answer]
    D --> G[✋ Human Approval]
    G --> H[📊 Execute SQL]
    H --> F
    E --> C
    E --> D

    C --> I[🌐 Tavily Web Search]
    I --> F

    style A fill:#e1f5e1
    style F fill:#e1f5e1
    style D fill:#fff4e6
    style G fill:#ffe6e6
```

</div>

---

## 🔒 Security Pipeline

Every request passes through **9 security layers** in a fixed order:

```mermaid
flowchart TD
    A[POST /query] --> B[L1: Pydantic Validation<br/>+ regex injection patterns]
    B --> C[L4a: JWT Auth]
    C --> D[L4b: Rate Limiting<br/>20 req/min]
    D --> E[L6: Token Budget<br/>100k/day]
    E --> F[L5: Input Restructuring<br/>truncate >3k | summarize >6k]
    F --> G[L2: Input Guard<br/>llm-guard scan]
    G --> H[L7a: Content Moderation<br/>+ PII Redaction]
    H --> I[LangGraph Invoke]
    I --> J[L3: Hardened System Prompt]
    J --> K[L8: Spotlighting<br/>XML-delimited chunks]
    K --> L[LLM Generation]
    L --> M[L7b: Output Moderation<br/>+ PII Redaction]
    M --> N[L9: Output Validation<br/>Pydantic + LLM retry]
    N --> O[Return ChatResponse]
```

| Layer | Module | What it does | Failure response |
|-------|--------|--------------|------------------|
| **L1** | `app/models.py` | Pydantic validation + regex injection patterns | `422 Unprocessable Entity` |
| **L4a** | `app/middleware/auth.py` | JWT verification | `401 Unauthorized` |
| **L4b** | `app/middleware/rate_limiter.py` | Per-user sliding-window rate limit (20 req/min) | `429 Too Many Requests` |
| **L6** | `app/security/token_budget.py` | Daily token budget check (100k tokens/day) | `429 Too Many Requests` |
| **L5** | `app/security/input_restructuring.py` | tiktoken-based truncate (>3k) or summarize (>6k) | — |
| **L2** | `app/security/input_guard.py` | llm-guard `PromptInjection`, `Toxicity`, `BanTopics` scan | `400 injection_blocked` |
| **L7a** | `app/security/content_moderation.py` | Input moderation + PII redaction | `400 content_blocked` |
| **L7b** | `app/security/content_moderation.py` | Output moderation + PII redaction | `500 output_blocked` |
| **L9** | `app/security/output_validator.py` | Pydantic schema validation with LLM retry (max 2) | `500 schema_failed` |

> Inside the LangGraph, two additional layers protect the LLM itself:
> - **L3 — Hardened system prompt** (`app/security/system_prompt.py`): Explicitly marks user messages as untrusted data.
> - **L8 — Spotlighting** (`app/security/spotlighting.py`): Wraps retrieved chunks in XML delimiters with a "data not instructions" preamble.

---

## 🧠 LangGraph State Machine

The heart of the system is a **LangGraph** compiled with a Postgres checkpointer for persistence and human-in-the-loop interrupts.

```mermaid
stateDiagram-v2
    [*] --> route_intent
    route_intent --> retrieve_rag : hybrid
    route_intent --> generate_sql_node : sql
    route_intent --> generate_answer : rag
    retrieve_rag --> generate_sql_node
    generate_sql_node --> request_sql_approval
    request_sql_approval --> execute_sql
    execute_sql --> generate_answer
    generate_answer --> finalize
    finalize --> [*]
```

### SQL Human-in-the-Loop Approval

```mermaid
sequenceDiagram
    actor U as User
    participant API as /query
    participant G as LangGraph
    participant SQL as SQLService
    participant DB as Postgres
    U->>API: Ask data question
    API->>G: graph.invoke(...)
    G->>SQL: generate_sql()
    SQL-->>G: SQL + explanation
    G->>G: interrupt() — pause
    G-->>API: pending_sql block
    API-->>U: "SQL approval required"
    U->>API: POST /query/sql/execute<br/>{query_id, approved}
    API->>G: Command(resume={approved})
    G->>DB: execute_sql() or skip
    DB-->>G: rows
    G->>G: generate_answer()
    G-->>API: final_answer
    API-->>U: ChatResponse
```

---

## 📚 RAG Retrieval Pipeline

```mermaid
flowchart LR
    Q[User Question] --> Cache1{Intent Cache?}
    Cache1 -->|miss| Intent[LLM Intent Classifier]
    Cache1 -->|hit| RAGPath
    Intent --> RAGPath

    subgraph RAGPath [RAG Path]
        direction TB
        Cache2{RAG Answer Cache?}
        Cache2 -->|hit| Return1[Return Cached Answer]
        Cache2 -->|miss| Retrieve

        Retrieve -->|hyde| HyDE[HyDE Retriever<br/>3 hypotheses]
        Retrieve -->|dense| Dense[Dense Vector Search]
        Retrieve -->|hybrid| Hybrid[Hybrid Dense + Sparse<br/>RRF fusion]

        HyDE --> Rerank[Reranker<br/>cross-encoder / voyage]
        Dense --> Rerank
        Hybrid --> Rerank

        Rerank --> CRAG[CRAG Grading<br/>gpt-4o-mini]
        CRAG -->|low relevance| Web[Tavily Web Search]
        CRAG -->|ok| Spotlight[Spotlighting]
        Web --> Spotlight

        Spotlight --> Gen[LLM Generate<br/>gpt-4o]
        Gen --> Reflect{Self-Reflect?}
        Reflect -->|needs regen| Gen
        Reflect -->|ok| Validate[Output Validate]
        Validate --> CacheSet[Cache Answer]
        CacheSet --> Return2[Return Answer]
    end
```

---

## ⚡ Caching Topology

Five cache tiers keep latency low and costs bounded. All backed by **Upstash Redis**.

```mermaid
flowchart TD
    Q[Query] --> C1[Intent Router Cache<br/>TTL: 24h]
    Q --> C2[RAG Answer Cache<br/>TTL: 1h]
    Q --> C3[SQL Generation Cache<br/>TTL: 24h]
    SQL[SQL Statement] --> C4[SQL Result Cache<br/>TTL: 15m]
    TXT[Text Chunk] --> C5[Embedding Cache<br/>TTL: 7d]
```

| Tier | Key | TTL | Purpose |
|------|-----|-----|---------|
| `rag_answer` | `sha256(question + flags)` | 1 hour | Full RAG/HYBRID answers |
| `sql_gen` | `sha256(question)` | 24 hours | Generated SQL statements |
| `sql_result` | `sha256(normalized SQL)` | 15 minutes | SELECT result rows |
| **embedding** | `sha256(text)` | 7 days | OpenAI embedding vectors |
| `intent_router` | `sha256(question.lower())` | 24 hours | Intent classification |

Doc deduplication (S3 or local FS) acts as a sixth, indefinite cache for uploaded file bodies keyed by SHA-256.

---

## 📄 Document Ingestion Flow

```mermaid
flowchart LR
    Upload[POST /documents/upload<br/>Admin JWT] --> Parse[Parse PDF<br/>docling / pypdf]
    Parse --> Chunk[Chunk + Metadata]
    Chunk --> Embed[OpenAI Embeddings]
    Embed --> Upsert[Upsert to Qdrant]
    Upsert --> Done[Searchable]
```

---

## 🚀 Quick Start

### Prerequisites

```bash
✅ Python 3.12+
✅ Docker & Docker Compose
✅ OpenAI API Key
✅ Upstash Redis URL + Token
✅ Tavily API Key (optional, for web-search fallback)
```

### Installation in 5 Steps

```bash
# 1️⃣ Create & activate virtual environment
uv venv
source .venv/bin/activate

# 2️⃣ Install dependencies
uv pip install -e ".[dev]"

# 3️⃣ Configure environment
cp .env.example .env
# Edit .env with your API keys

# 4️⃣ Start infrastructure
docker compose up -d

# 5️⃣ Seed database & run
python scripts/seed_db.py
uvicorn app.main:app --reload
```

🎉 **Done!** API running at http://localhost:8000 • Docs at http://localhost:8000/docs

### Optional: Launch Streamlit Tester

```bash
streamlit run scripts/streamlit_app.py
```

Provides a visual UI for auth, upload, query, and SQL approval.

---

## 📡 API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | Public (IP rate limited) | Register a new support agent |
| `POST` | `/auth/login` | Public (IP rate limited) | Login and receive a JWT |
| `POST` | `/query` | Bearer JWT | Ask a question — RAG, SQL, or HYBRID |
| `POST` | `/query/sql/execute` | Bearer JWT | Approve or reject generated SQL |
| `POST` | `/documents/upload` | Admin JWT | Upload and index a PDF |
| `GET` | `/admin/health` | Public | Dependency health checks |
| `GET` | `/admin/cache/stats` | Admin JWT | Per-tier cache telemetry |

### 1️⃣ Register & Login

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "agent@demo.local", "password": "demo1234"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "agent@demo.local", "password": "demo1234"}'
# → copy the "token" value
```

### 2️⃣ Ask a RAG Question

```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is our return policy?",
    "search_mode": "hybrid",
    "enable_hyde": false,
    "enable_rerank": true,
    "enable_crag": true,
    "top_k": 5
  }'
```

### 3️⃣ Ask a SQL Question

```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many orders were placed last month?"
  }'
# → may return pending_sql block
```

### 4️⃣ Approve SQL Execution

```bash
curl -X POST http://localhost:8000/query/sql/execute \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query_id": "<query_id>",
    "approved": true
  }'
```

### 5️⃣ Upload a Document (Admin)

```bash
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer <admin_token>" \
  -F "file=@policy.pdf"
```

---

## 🎛️ Feature Flags

`POST /query` accepts a `QueryRequest` body with these per-request toggles:

| Flag | Default | Description |
|------|---------|-------------|
| `enable_hyde` | `false` | HyDE — generate hypothetical answer embeddings to improve retrieval |
| `enable_rerank` | `true` | Cross-encoder reranking of retrieved chunks |
| `enable_crag` | `true` | CRAG relevance grading + Tavily web-search fallback |
| `enable_self_reflective` | `false` | Self-RAG reflection loop (max 2 retries) |
| `search_mode` | `"hybrid"` | Retrieval mode: `dense`, `sparse`, or `hybrid` |
| `top_k` | `5` | Number of chunks to retrieve (1–50) |

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run only unit tests (no external services needed)
pytest tests/unit/

# Run integration tests (requires docker compose up)
pytest tests/integration/

# Lint and format check
ruff check .
ruff format --check .

# Type check
mypy app/

# Eval harness (Ragas on 50-question seed set)
make eval
```

---

## 📁 Project Structure

```
My_project/
├── 📱 app/
│   ├── api/              # 🚀 FastAPI endpoints (auth, query, upload, admin)
│   ├── core/             # 🧠 LangGraph state machine + retrieval orchestrator
│   ├── middleware/       # 🔐 JWT auth + rate limiting
│   ├── security/         # 🛡️ 9 security layers as discrete modules
│   ├── services/         # 🛠️ RAG, SQL, cache, vector, embedding, web search
│   ├── storage/          # 📦 S3 + local storage backends
│   ├── main.py           # FastAPI app factory
│   ├── models.py         # 📊 Pydantic request/response models
│   └── config.py         # ⚙️ pydantic-settings env loader
├── 🧪 tests/
│   ├── unit/             # ✅ Per-module behavior tests (mocked, fast)
│   └── integration/      # 🔗 Full request/response flows (needs live infra)
├── 📜 scripts/           # Seed, eval, serve, streamlit demo
├── 🌱 seed/              # Postgres seed data + demo PDFs
├── 🏗️ infra/             # CloudFormation for AWS deployment
├── .env.example          # 🔐 Config template
├── docker-compose.yml    # 🐳 Postgres + Qdrant + App
├── pyproject.toml        # 📦 Dependencies + tool config
└── Dockerfile            # 🐳 Production image
```

---

## ⚙️ Configuration

Key settings in `.env`:

```bash
# 🤖 LLM Configuration
OPENAI_API_KEY=sk-...
LLM_MODEL_ANSWER=gpt-4o
LLM_MODEL_GRADER=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# 🗄️ Database & Vector Store
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/adv_rag
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=documents

# 💾 Cache (Upstash Redis)
UPSTASH_REDIS_URL=https://...
UPSTASH_REDIS_TOKEN=...
CACHE_TTL_RAG=3600
CACHE_TTL_SQL_GEN=86400
CACHE_TTL_EMBEDDINGS=604800

# 🔐 Auth & Security
JWT_SECRET=change-me
RATE_LIMIT_REQUESTS=20
MAX_TOKENS_PER_USER_DAILY=100000

# 🔍 Retrieval Settings
HYBRID_SEARCH_ENABLED=true
RRF_K=60
RERANKER_BACKEND=local
CRAG_RELEVANCE_THRESHOLD=0.7
REFLECTION_MIN_SCORE=0.8

# 🌐 Web Search
TAVILY_API_KEY=tvly-...

# 📦 Storage
STORAGE_BACKEND=local
S3_CACHE_BUCKET=adv-rag-cache
```

See `.env.example` for the complete list.

---

## 🚀 Deployment

AWS deployment is handled via **CloudFormation** in `infra/cloudformation.yaml` and GitHub Actions CI/CD with OIDC authentication. The stack runs as a single **ECS Fargate** task with sidecar containers (app, Qdrant, Postgres) backed by **EFS** for persistence.

See `docs/DEPLOYMENT_GUIDE.md` for deployment details.

---

## 🛠️ Technology Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com) — Modern Python API framework
- **Orchestration**: [LangGraph](https://langchain.com/langgraph) — Agent state machines with human-in-the-loop
- **Vector DB**: [Qdrant](https://qdrant.tech) — High-performance vector search
- **Database**: [PostgreSQL](https://www.postgresql.org) — Relational data + LangGraph checkpoints
- **Cache**: [Upstash Redis](https://upstash.com) — Serverless Redis for caching & rate limits
- **LLM**: [OpenAI GPT-4o](https://openai.com) — Language model + embeddings
- **Security**: [llm-guard](https://llm-guard.com) — Input scanning + moderation
- **Web Search**: [Tavily](https://tavily.com) — AI search API fallback
- **Document Parsing**: [Docling](https://github.com/DS4SD/docling) — PDF/MD parsing
- **Deployment**: [AWS CloudFormation](https://aws.amazon.com/cloudformation/) + ECS Fargate

---

## 📄 License

MIT License

---

<div align="center">

### ⚡ Production-Ready RAG with Text2SQL, Security, and Caching

**Built for e-commerce customer support — safe, fast, and observable**

🌟 **Star this repo if you find it useful!** 🌟

</div>
