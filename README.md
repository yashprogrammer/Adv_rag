# ADV RAG

E-commerce Customer Support Copilot — Text2SQL + Core RAG + Caching + LLM Security.

## Quick start

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your OpenAI, Upstash Redis, and Tavily credentials
```

### 3. Start local infrastructure

```bash
docker compose up -d
```

This brings up Postgres (port 5432) and Qdrant (port 6333).

### 4. Seed the database

```bash
python scripts/seed_db.py
```

### 5. Run the API

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

---

## API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | Public (IP rate limited) | Register a new support agent |
| `POST` | `/auth/login` | Public (IP rate limited) | Login and receive a JWT |
| `POST` | `/query` | Bearer JWT | Ask a question — RAG, SQL, or HYBRID |
| `POST` | `/query/sql/execute` | Bearer JWT | Approve or reject generated SQL |
| `POST` | `/documents/upload` | Admin JWT | Upload and index a PDF |
| `GET` | `/admin/health` | Public | Dependency health checks |
| `GET` | `/admin/cache/stats` | Admin JWT | Per-tier cache telemetry |

### Example: login and query

```bash
# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "agent@demo.local", "password": "demo"}'

# Ask a RAG question
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is our return policy?"}'
```

---

## Feature flags

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

## Security layers overview

The `/query` pipeline composes 9 security layers in a fixed order:

| Layer | Module | What it does | Failure response |
|-------|--------|--------------|------------------|
| **L1** | `app/models.py` | Pydantic validation + regex injection patterns | `422 Unprocessable Entity` |
| **L4a** | `app/middleware/auth.py` | JWT verification | `401 Unauthorized` |
| **L4b** | `app/middleware/rate_limiter.py` | Per-user sliding-window rate limit (default 20 req/min) | `429 Too Many Requests` |
| **L6** | `app/security/token_budget.py` | Daily token budget check (default 100k tokens/day) | `429 Too Many Requests` |
| **L5** | `app/security/input_restructuring.py` | tiktoken-based truncate (>3k) or summarize (>6k) | — |
| **L2** | `app/security/input_guard.py` | llm-guard `PromptInjection`, `Toxicity`, `BanTopics` scan | `400 injection_blocked` |
| **L7a** | `app/security/content_moderation.py` | Input moderation + PII redaction | `400 content_blocked` |
| **L7b** | `app/security/content_moderation.py` | Output moderation + PII redaction | `500 output_blocked` |
| **L9** | `app/security/output_validator.py` | Pydantic schema validation with LLM retry (max 2) | `500 schema_failed` |

Inside the LangGraph, two additional layers protect the LLM itself:

- **L3 — Hardened system prompt** (`app/security/system_prompt.py`): Explicitly marks user messages as untrusted data.
- **L8 — Spotlighting** (`app/security/spotlighting.py`): Wraps retrieved chunks in XML delimiters with a "data not instructions" preamble.

---

## Caching topology

Five cache tiers keep latency low and costs bounded:

| Tier | Key | TTL | Purpose |
|------|-----|-----|---------|
| `rag_answer` | `sha256(question + flags)` | 1 hour | Full RAG/HYBRID answers |
| `sql_gen` | `sha256(question)` | 24 hours | Generated SQL statements |
| `sql_result` | `sha256(normalized SQL)` | 15 minutes | SELECT result rows |
| **embedding** | `sha256(text)` | 7 days | OpenAI embedding vectors |
| `intent_router` | `sha256(question.lower())` | 24 hours | Intent classification |

Doc deduplication (S3 or local FS) acts as a sixth, indefinite cache for uploaded file bodies keyed by SHA-256.

---

## Local test commands

```bash
# Run all tests
pytest

# Run only unit tests
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

## Project structure

```
app/
  api/           # FastAPI route handlers (thin)
  core/          # LangGraph state machine, retrieval orchestrator
  middleware/    # Auth, rate limiting
  security/      # 9 security layers as discrete modules
  services/      # RAG, SQL, cache, vector, embedding, etc.
  storage/       # S3 + local storage backends
tests/
  unit/          # Per-module behavior tests
  integration/   # Full request/response flows
scripts/         # Seed, eval, streamlit demo
seed/            # Postgres seed data + demo PDFs
infra/           # Terraform for AWS deployment
```

---

## Key environment variables

See `.env.example` for the full list. The most important ones:

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | LLM + embeddings |
| `UPSTASH_REDIS_URL` / `UPSTASH_REDIS_TOKEN` | Cache, rate limits, token budget |
| `DATABASE_URL` | Postgres (users + e-commerce schema + LangGraph checkpoints) |
| `QDRANT_URL` | Vector database |
| `TAVILY_API_KEY` | Web-search fallback |
| `JWT_SECRET` | Bearer token signing |

---

## Deployment

AWS deployment is handled via Terraform in `infra/terraform/` and GitHub Actions CI/CD with OIDC authentication. The stack runs as a single ECS Fargate task with sidecar containers (app, Qdrant, Postgres) backed by EFS for persistence.

See `infra/terraform/README.md` for deployment details.

---

## License

MIT
