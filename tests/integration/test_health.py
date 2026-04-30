"""Integration tests for /admin/health endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/admin/health")
    assert response.status_code == 200


def test_health_response_schema(client: TestClient) -> None:
    response = client.get("/admin/health")
    data = response.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    assert isinstance(data.get("qdrant"), bool)
    assert isinstance(data.get("postgres"), bool)
    assert isinstance(data.get("redis"), bool)
    assert isinstance(data.get("openai"), bool)
