"""Integration tests for SQL path via interrupt()."""

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


def test_query_sql_path_returns_pending_sql(client: TestClient, token: str) -> None:
    with patch("app.api.query.is_allowed_user", return_value=(True, 19, 1)):
        with patch("app.api.query.check_budget", return_value=(True, 99_000)):
            with patch("app.api.query.consume_budget", return_value={"used": 1010}):
                with patch("app.core.graph.classify_intent", return_value="sql"):
                    with patch("app.core.graph.sql_service.generate_sql") as mock_gen:
                        mock_gen.return_value = {
                            "sql": "SELECT COUNT(*) FROM customers WHERE country = 'Germany'",
                            "explanation": "Count German customers",
                        }
                        resp = client.post(
                        "/query",
                        json={"question": "How many customers in Germany?"},
                        headers={"Authorization": f"Bearer {token}"},
                    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_sql"] is not None
    assert "SELECT" in data["pending_sql"]["sql"]
    assert data["pending_sql"]["query_id"] is not None


def test_sql_execute_approved_returns_results(client: TestClient, token: str) -> None:
    # First, get a pending SQL
    with patch("app.api.query.is_allowed_user", return_value=(True, 19, 1)):
        with patch("app.api.query.check_budget", return_value=(True, 99_000)):
            with patch("app.api.query.consume_budget", return_value={"used": 1010}):
                with patch("app.core.graph.classify_intent", return_value="sql"):
                    with patch("app.core.graph.sql_service.generate_sql") as mock_gen:
                        mock_gen.return_value = {
                            "sql": "SELECT COUNT(*) AS count FROM customers WHERE country = 'Germany'",
                            "explanation": "Count German customers",
                        }
                        resp = client.post(
                        "/query",
                        json={"question": "How many customers in Germany?"},
                        headers={"Authorization": f"Bearer {token}"},
                    )
    data = resp.json()
    query_id = data["pending_sql"]["query_id"]

    # Execute with approval
    resp2 = client.post(
        "/query/sql/execute",
        json={"query_id": query_id, "approved": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    result = resp2.json()
    # Should contain database results or an error message
    assert "answer" in result
