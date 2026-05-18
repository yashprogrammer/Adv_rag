"""Unit test: every L1 module imports cleanly.

L1 adds naive-RAG modules:
  - app.services.embedding_service
  - app.services.vector_store  (dense only)
  - app.services.document_processor
  - app.services.llm_service
  - app.services.rag_service
  - app.services.query_cache_service  (embedding cache only; full caching in L8)
  - app.api.query
"""

import pytest

MODULES = [
    "app.config",
    "app.main",
    "app.api.admin",
    "app.api.auth",
    "app.api.query",
    "app.core.state",
    "app.middleware.auth",
    "app.middleware.rate_limiter",
    "app.security.input_guard",
    "app.security.system_prompt",
    "app.security.content_moderation",
    "app.security.input_restructuring",
    "app.security.token_budget",
    "app.security.output_validator",
    "app.security.spotlighting",
    "app.services.embedding_service",
    "app.services.vector_store",
    "app.services.sparse_vector_service",
    "app.services.reranking",
    "app.services.document_processor",
    "app.services.llm_service",
    "app.services.rag_service",
    "app.services.query_cache_service",
    "app.storage.storage_backend",
    "app.storage.s3_storage",
    "app.storage.local_storage",
]


@pytest.mark.parametrize("mod", MODULES)
def test_import(mod: str) -> None:
    __import__(mod)
