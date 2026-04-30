"""Unit test: every top-level app module imports cleanly."""

import pytest

MODULES = [
    "app.config",
    "app.main",
    "app.api.admin",
    "app.core.state",
    "app.core.graph",
    "app.core.retrieval",
    "app.middleware.auth",
    "app.middleware.rate_limiter",
    "app.security.input_guard",
    "app.security.system_prompt",
    "app.security.content_moderation",
    "app.security.input_restructuring",
    "app.security.token_budget",
    "app.security.output_validator",
    "app.security.spotlighting",
    "app.services.sql_service",
    "app.services.rag_service",
    "app.services.router_service",
    "app.services.crag",
    "app.services.self_reflective",
    "app.services.hyde",
    "app.services.reranking",
    "app.services.vector_store",
    "app.services.sparse_vector_service",
    "app.services.embedding_service",
    "app.services.document_processor",
    "app.services.llm_service",
    "app.services.web_search",
    "app.services.query_cache_service",
    "app.services.doc_cache_service",
    "app.services.pdf_ingestion",
    "app.storage.storage_backend",
    "app.storage.s3_storage",
    "app.storage.local_storage",
]


@pytest.mark.parametrize("mod", MODULES)
def test_import(mod: str) -> None:
    __import__(mod)
