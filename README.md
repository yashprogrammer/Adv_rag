# ADV RAG — E-commerce Customer Support Copilot

A FastAPI service that answers support questions using Text2SQL + RAG with advanced retrieval, caching, and security layers.

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- `uv` (`pip install uv`)

### Local Development

1. **Clone and configure:**
   ```bash
   git clone <repo>
   cd adv-rag
   cp .env.example .env
   # Edit .env with your OPENAI_API_KEY and other secrets
   ```

2. **Set up commit template:**
   ```bash
   git config commit.template .gitmessage
   ```

3. **Install dependencies:**
   ```bash
   uv pip install -e ".[dev]"
   ```

4. **Start the stack:**
   ```bash
   docker compose up
   ```
   This brings up Postgres, Qdrant, and the FastAPI app. The app waits for the other two healthchecks before starting.

5. **Verify:**
   ```bash
   curl http://localhost:8000/admin/health
   ```
   Expected: `{"status":"ok","qdrant":true,"postgres":true,"redis":false,"openai":false}`

### Running Tests

```bash
pytest          # all tests
ruff check .    # lint
ruff format .   # format
mypy app/       # type check
```

## Architecture

```
Postgres (:5432) ←→ FastAPI (:8000) ←→ Qdrant (:6333)
                        ↕
                   Upstash Redis (HTTP)
                   OpenAI API
```

## API Surface

| Endpoint | Auth | Description |
|---|---|---|
| `GET /admin/health` | Public | Dependency-aware health check |

More endpoints will be added in subsequent phases.

## Phases

- **Phase 0** — Security baseline
- **Phase 1** — Skeleton + LangGraph wired *(current)*
- **Phase 2** — Retrieval quality
- **Phase 3** — Self-correction
- **Phase 4** — Caching + harden
- **Phase 5** — AWS deployment

## Configuration

All settings are in `app/config.py` via `pydantic_settings.BaseSettings`. See `.env.example` for every available key.
