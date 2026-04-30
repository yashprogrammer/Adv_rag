"""Unit tests for secure PDF ingestion helpers."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.services.pdf_ingestion import (
    PDFIngestionError,
    cleanup_temp_file,
    ingest_pdf_upload,
    sanitize_filename,
)


class DummyUploadFile:
    def __init__(self, payload: bytes, filename: str, content_type: str) -> None:
        self._payload = payload
        self.filename = filename
        self.content_type = content_type

    async def read(self) -> bytes:
        return self._payload


def test_sanitize_filename_strips_path_and_invalid_characters() -> None:
    assert sanitize_filename("../../weird name?.pdf") == "weird_name_.pdf"


def test_ingest_rejects_non_pdf_content_type() -> None:
    file = DummyUploadFile(b"%PDF-1.7\n", "sample.pdf", "text/plain")

    with pytest.raises(PDFIngestionError, match="Only PDF"):
        asyncio.run(ingest_pdf_upload(file))


def test_ingest_rejects_oversized_pdf() -> None:
    payload = b"%PDF-1.7\n" + (b"A" * 64)
    file = DummyUploadFile(payload, "sample.pdf", "application/pdf")

    with pytest.raises(PDFIngestionError, match="size limit"):
        asyncio.run(ingest_pdf_upload(file, max_file_size_bytes=16))


def test_ingest_rejects_invalid_pdf_magic_header() -> None:
    file = DummyUploadFile(b"NOT_A_PDF", "sample.pdf", "application/pdf")

    with pytest.raises(PDFIngestionError, match="valid PDF"):
        asyncio.run(ingest_pdf_upload(file))


def test_ingest_writes_temp_file_and_cleanup() -> None:
    payload = b"%PDF-1.4\n%EOF"
    file = DummyUploadFile(payload, "safe.pdf", "application/pdf")

    ingested = asyncio.run(ingest_pdf_upload(file))
    assert Path(ingested.temp_path).exists()
    assert ingested.safe_filename == "safe.pdf"
    cleanup_temp_file(ingested.temp_path)
    assert not Path(ingested.temp_path).exists()


def test_ingest_rejects_when_page_count_limit_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"%PDF-1.4\n%EOF"
    file = DummyUploadFile(payload, "safe.pdf", "application/pdf")

    monkeypatch.setattr("app.services.pdf_ingestion._count_pdf_pages_best_effort", lambda _: 12)
    with pytest.raises(PDFIngestionError, match="page count limit"):
        asyncio.run(ingest_pdf_upload(file, max_pages=10))
