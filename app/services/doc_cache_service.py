"""Document deduplication metadata cache service."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from app.storage.storage_backend import StorageBackend, get_storage_backend

logger = logging.getLogger(__name__)


class DocCacheService:
    """Stores and retrieves document metadata by content hash."""

    def __init__(self, backend: StorageBackend | None = None):
        self.backend = backend or get_storage_backend()

    def compute_content_hash(self, content: bytes) -> str:
        """Compute a sha256 hex digest from content bytes."""
        return hashlib.sha256(content).hexdigest()

    def compute_file_hash(self, file_path: str | Path, chunk_size: int = 8192) -> str:
        """Compute sha256 hex digest from a file with chunked reads."""
        digest = hashlib.sha256()
        path = Path(file_path)
        with path.open("rb") as file_obj:
            while True:
                chunk = file_obj.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def _metadata_key(self, content_hash: str) -> str:
        return f"{content_hash}/metadata.json"

    def exists(self, content_hash: str) -> bool:
        """Return whether metadata exists for a document hash."""
        return self.backend.exists(self._metadata_key(content_hash))

    def set_metadata(self, content_hash: str, metadata: dict[str, Any]) -> bool:
        """Persist metadata JSON for a content hash."""
        try:
            payload = json.dumps(metadata).encode("utf-8")
            self.backend.save_bytes(self._metadata_key(content_hash), payload)
            return True
        except Exception:
            logger.exception("Failed to store document metadata hash=%s", content_hash)
            return False

    def get_metadata(self, content_hash: str) -> dict[str, Any] | None:
        """Load metadata JSON for a content hash."""
        key = self._metadata_key(content_hash)
        if not self.backend.exists(key):
            return None

        try:
            data = self.backend.read_bytes(key)
            return json.loads(data.decode("utf-8"))
        except Exception:
            logger.exception("Failed to read document metadata hash=%s", content_hash)
            return None
