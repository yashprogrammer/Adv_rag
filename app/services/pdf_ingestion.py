"""Secure PDF ingestion helpers for upload pipeline."""

from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

DEFAULT_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
}


class PDFIngestionError(ValueError):
    """Raised when an upload fails secure PDF validation."""


@dataclass(frozen=True)
class IngestedPDF:
    temp_path: str
    safe_filename: str
    size_bytes: int
    page_count: int | None = None


def sanitize_filename(filename: str | None) -> str:
    """Return a path-safe PDF filename."""
    raw = Path(filename or "upload.pdf").name
    sanitized = "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "_" for ch in raw)
    sanitized = sanitized.strip("._") or "upload"
    if not sanitized.lower().endswith(".pdf"):
        sanitized = f"{sanitized}.pdf"
    return sanitized


def cleanup_temp_file(path: str) -> None:
    """Delete temp file if it exists."""
    try:
        os.remove(path)
    except FileNotFoundError:
        return


def _count_pdf_pages_best_effort(pdf_bytes: bytes) -> int | None:
    try:
        from pypdf import PdfReader
    except Exception:
        return None

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return len(reader.pages)
    except Exception:
        return None


async def ingest_pdf_upload(
    file: UploadFile,
    *,
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    allowed_content_types: set[str] | None = None,
    max_pages: int | None = None,
) -> IngestedPDF:
    """Validate uploaded PDF and persist to a temp file."""
    content_types = allowed_content_types or DEFAULT_ALLOWED_CONTENT_TYPES
    if file.content_type not in content_types:
        raise PDFIngestionError("Only PDF files are accepted")

    payload = await file.read()
    size_bytes = len(payload)
    if size_bytes == 0:
        raise PDFIngestionError("Uploaded PDF is empty")
    if size_bytes > max_file_size_bytes:
        raise PDFIngestionError("Uploaded PDF exceeds file size limit")
    if not payload.startswith(b"%PDF-"):
        raise PDFIngestionError("Uploaded file is not a valid PDF")

    page_count = _count_pdf_pages_best_effort(payload)
    if max_pages is not None and page_count is not None and page_count > max_pages:
        raise PDFIngestionError("Uploaded PDF exceeds page count limit")

    safe_filename = sanitize_filename(file.filename)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="upload_")
    try:
        tmp.write(payload)
        tmp.flush()
        return IngestedPDF(
            temp_path=tmp.name,
            safe_filename=safe_filename,
            size_bytes=size_bytes,
            page_count=page_count,
        )
    except Exception:
        cleanup_temp_file(tmp.name)
        raise
    finally:
        tmp.close()
