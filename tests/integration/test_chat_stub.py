"""Integration tests for stub /chat endpoint with rate limit + token budget."""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@127.0.0.1:5432/adv_rag"

from app.main import app  # noqa: E402
from app.middleware.auth import create_access_token  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def token() -> str:
    return create_access_token("tester@demo.local")


def test_chat_stub_returns_200_with_budget_and_rate_limit(client: TestClient, token: str) -> None:
    with patch("app.api.chat.is_allowed_user", return_value=(True, 19, 1)):
        with patch("app.api.chat.check_budget", return_value=(True, 99_000)):
            with patch("app.api.chat.consume_budget", return_value={"used": 1010, "limit": 100000, "remaining": 98990}):
                resp = client.post(
                    "/chat",
                    json={"message": "hello"},
                    headers={"Authorization": f"Bearer {token}"},
                )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "stub"
    assert data["cache_hit"] is False


def test_chat_stub_rate_limited(client: TestClient, token: str) -> None:
    with patch("app.api.chat.is_allowed_user", return_value=(False, 0, 21)):
        resp = client.post(
            "/chat",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 429


def test_chat_stub_budget_exhausted(client: TestClient, token: str) -> None:
    with patch("app.api.chat.is_allowed_user", return_value=(True, 19, 1)):
        with patch("app.api.chat.check_budget", return_value=(False, 100)):
            resp = client.post(
                "/chat",
                json={"message": "hello"},
                headers={"Authorization": f"Bearer {token}"},
            )
    assert resp.status_code == 429
    assert "remaining" in resp.json()["detail"].lower() or "tokens" in resp.json()["detail"].lower()
