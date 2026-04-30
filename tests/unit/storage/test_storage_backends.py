"""Unit tests for storage backends and factory."""

import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.storage.local_storage import LocalStorage
from app.storage.s3_storage import S3Storage
from app.storage.storage_backend import get_storage_backend


def test_local_storage_roundtrip(tmp_path: Path) -> None:
    storage = LocalStorage(base_dir=str(tmp_path / "cache"))
    key = "docs/a.bin"
    data = b"hello"

    assert storage.exists(key) is False
    storage.save_bytes(key, data)
    assert storage.exists(key) is True
    assert storage.read_bytes(key) == data
    assert storage.url_for(key).startswith("file://")


def test_s3_storage_roundtrip_with_injected_client() -> None:
    class FakeS3:
        def __init__(self):
            self._store: dict[tuple[str, str], bytes] = {}

        def head_object(self, Bucket: str, Key: str) -> None:
            if (Bucket, Key) not in self._store:
                exc = Exception("not found")
                exc.response = {"Error": {"Code": "404"}}  # type: ignore[attr-defined]
                raise exc

        def put_object(self, Bucket: str, Key: str, Body: bytes) -> None:
            self._store[(Bucket, Key)] = Body

        def get_object(self, Bucket: str, Key: str):
            return {"Body": io.BytesIO(self._store[(Bucket, Key)])}

    client = FakeS3()
    storage = S3Storage(bucket="b", region="us-east-1", client=client)
    key = "k/x.bin"

    assert storage.exists(key) is False
    storage.save_bytes(key, b"123")
    assert storage.exists(key) is True
    assert storage.read_bytes(key) == b"123"
    assert storage.url_for(key) == "s3://b/k/x.bin"


def test_s3_storage_raises_when_boto3_missing() -> None:
    original = sys.modules.pop("boto3", None)
    sys.modules["boto3"] = None  # type: ignore[assignment]
    try:
        with pytest.raises(RuntimeError, match="boto3 is required"):
            S3Storage(bucket="b", region="us-east-1")
    finally:
        if original is None:
            sys.modules.pop("boto3", None)
        else:
            sys.modules["boto3"] = original


def test_storage_factory_local(monkeypatch) -> None:
    monkeypatch.setattr("app.storage.storage_backend.settings.storage_backend", "local")
    backend = get_storage_backend()
    assert isinstance(backend, LocalStorage)


def test_storage_factory_invalid(monkeypatch) -> None:
    monkeypatch.setattr("app.storage.storage_backend.settings.storage_backend", "unknown")
    with pytest.raises(ValueError, match="Unsupported storage backend"):
        get_storage_backend()


def test_storage_factory_s3(monkeypatch) -> None:
    class FakeBoto3Module:
        @staticmethod
        def client(_name: str, region_name: str):
            return SimpleNamespace(region_name=region_name)

    monkeypatch.setattr("app.storage.storage_backend.settings.storage_backend", "s3")
    monkeypatch.setattr("app.storage.s3_storage.settings.s3_cache_bucket", "bucket")
    monkeypatch.setattr("app.storage.s3_storage.settings.aws_region", "us-east-1")
    monkeypatch.setitem(sys.modules, "boto3", FakeBoto3Module())

    backend = get_storage_backend()
    assert isinstance(backend, S3Storage)
