"""Unit test: every L0 module imports cleanly.

Lesson 0 — the RAG services don't exist yet. Modules added in L1+:
  - app.core.graph, app.core.retrieval
  - app.services.*  (all RAG/SQL/cache services)
"""

import pytest

MODULES = [
    "app.config",
    "app.main",
    "app.api.admin",
    "app.api.auth",
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
    "app.storage.storage_backend",
    "app.storage.s3_storage",
    "app.storage.local_storage",
]


@pytest.mark.parametrize("mod", MODULES)
def test_import(mod: str) -> None:
    __import__(mod)
