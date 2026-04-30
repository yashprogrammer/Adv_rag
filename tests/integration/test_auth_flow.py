"""Integration test for auth register -> login -> protected resource flow."""

import os
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Force connection to Docker Postgres (127.0.0.1) instead of local Postgres on localhost
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@127.0.0.1:5432/adv_rag"

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_register_and_login_flow(client: TestClient) -> None:
    with patch("app.api.auth.is_allowed_ip", return_value=(True, 5, 0)):
        username = f"testuser_{uuid.uuid4().hex[:8]}@demo.local"
        # Register
        resp = client.post("/auth/register", json={"username": username, "password": "testpass"})
        assert resp.status_code == 201
        data = resp.json()
        assert "token" in data

        # Login
        resp = client.post("/auth/login", json={"username": username, "password": "testpass"})
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        token = data["token"]

    # Use token on a protected endpoint (stub for now — /admin/cache/stats is admin-only)
    # For integration we just verify the token decodes correctly by calling a protected endpoint
    # We'll test with /admin/cache/stats but since no admin flag, it should 403
    resp = client.get("/admin/cache/stats", headers={"Authorization": f"Bearer {token}"})
    # 403 because testuser is not admin, but auth itself worked (would be 401 if token bad)
    assert resp.status_code == 403


def test_login_wrong_password(client: TestClient) -> None:
    with patch("app.api.auth.is_allowed_ip", return_value=(True, 5, 0)):
        username = f"wrongpass_{uuid.uuid4().hex[:8]}@demo.local"
        client.post("/auth/register", json={"username": username, "password": "right"})
        resp = client.post("/auth/login", json={"username": username, "password": "wrong"})
    assert resp.status_code == 401


def test_register_duplicate_user(client: TestClient) -> None:
    with patch("app.api.auth.is_allowed_ip", return_value=(True, 5, 0)):
        username = f"dup_{uuid.uuid4().hex[:8]}@demo.local"
        client.post("/auth/register", json={"username": username, "password": "pass"})
        resp = client.post("/auth/register", json={"username": username, "password": "pass"})
    assert resp.status_code == 409
