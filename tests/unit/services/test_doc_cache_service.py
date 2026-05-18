"""Unit tests for document metadata dedup cache service."""

from pathlib import Path

from app.services.doc_cache_service import DocCacheService
from app.storage.local_storage import LocalStorage


def test_compute_file_hash_is_deterministic(tmp_path: Path) -> None:
    file_path = tmp_path / "doc.txt"
    file_path.write_text("same content", encoding="utf-8")

    svc = DocCacheService(backend=LocalStorage(base_dir=str(tmp_path / "cache")))
    hash_a = svc.compute_file_hash(file_path)
    hash_b = svc.compute_file_hash(file_path)

    assert hash_a == hash_b
    assert len(hash_a) == 64


def test_set_get_and_exists_metadata_roundtrip(tmp_path: Path) -> None:
    svc = DocCacheService(backend=LocalStorage(base_dir=str(tmp_path / "cache")))
    content_hash = svc.compute_content_hash(b"abc")
    payload = {"filename": "doc.pdf", "chunks": 8}

    assert svc.exists(content_hash) is False
    assert svc.set_metadata(content_hash, payload) is True
    assert svc.exists(content_hash) is True
    assert svc.get_metadata(content_hash) == payload
