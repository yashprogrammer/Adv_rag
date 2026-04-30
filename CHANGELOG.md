# ADV RAG Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses phase-based milestones instead of semantic versioning.

## [phase-0-baseline] — TBD

### Added
- JWT auth + bcrypt password hashing
- Sliding-window rate limit (per-user; per-IP for /auth/*)
- Token budget per user/day
- Pydantic input validation + regex pre-filter
- Hardened system prompt (e-commerce domain)
- Output schema validation with retry-with-LLM-error
- Spotlighting wrapper

## [phase-1-skeleton] — TBD

### Added
- FastAPI app with /query, /documents/upload, /admin/health endpoints
- LangGraph orchestration (route_intent -> generate_answer skeleton)
- Postgres + Qdrant docker-compose for local dev
- Vanna 2.0 wrapper with information_schema introspection
- Naive RAG path (embed -> cosine top-k -> spotlight -> generate)
