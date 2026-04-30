"""Integration tests for secure upload validation pipeline."""

import os

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
    return create_access_token("uploader@demo.local")


def test_upload_rejects_non_pdf_content_type(client: TestClient, token: str) -> None:
    resp = client.post(
        "/documents/upload",
        files={"file": ("sample.txt", b"hello", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 415
    assert "pdf" in resp.json()["detail"].lower()


def test_upload_rejects_oversized_pdf(client: TestClient, token: str) -> None:
    oversized = b"%PDF-1.7\n" + (b"0" * (10 * 1024 * 1024 + 1))
    resp = client.post(
        "/documents/upload",
        files={"file": ("big.pdf", oversized, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 413


def test_upload_rejects_malformed_pdf(client: TestClient, token: str) -> None:
    resp = client.post(
        "/documents/upload",
        files={"file": ("bad.pdf", b"not-a-real-pdf", "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 400
    assert "valid pdf" in resp.json()["detail"].lower()
