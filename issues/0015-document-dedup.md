# #15 — Document dedup cache (StorageBackend ABC + S3 + local FS)

## Parent PRD

#<prd-issue-number-tbd>

## What to build

The L5 cache layer from Doc 1 §4.6: SHA-256 the file body, and if we've parsed+chunked+embedded it before, skip all that work and just re-upsert the cached chunks/embeddings into Qdrant. Backend swappable between local FS (dev) and S3 (prod) via `STORAGE_BACKEND` env, behind a `StorageBackend` ABC with four methods (`put`, `get`, `exists`, `delete`).

After this slice, re-uploading the same PDF (under any filename) returns in <1s instead of 30s.

## Topology

```mermaid
flowchart TB
    Upload[POST /documents/upload] --> Hash[SHA-256 of file bytes<br/>= doc_id]
    Hash --> Exists{storage.exists doc_id}
    Exists -->|YES| Load[storage.get doc_id<br/>chunks.json + embeddings.npy + metadata.json]
    Load --> Reupsert[Qdrant upsert<br/>cached chunks + vectors]
    Reupsert --> Resp1([200 cache_hit])

    Exists -->|NO| Parse[Docling parse]
    Parse --> Chunk[HybridChunker]
    Chunk --> Embed[OpenAI embed batch]
    Embed --> Qdrant[Qdrant upsert]
    Qdrant --> Save[storage.put doc_id<br/>save chunks + embeddings + metadata]
    Save --> Resp2([200 cache_miss])

    subgraph Backend["StorageBackend ABC"]
        Local[LocalStorageBackend<br/>./cache/{doc_id}/]
        S3[S3StorageBackend<br/>s3://bucket/{doc_id}/]
    end
```

## Acceptance criteria

- [ ] `app/storage/storage_backend.py` — ABC with `put(key, data: bytes)`, `get(key) -> bytes`, `exists(key) -> bool`, `delete(key)`. Sub-paths under `key` allowed (e.g. `key="abc123/chunks.json"`).
- [ ] `app/storage/local_storage.py` — files under `./cache/`. Default in dev.
- [ ] `app/storage/s3_storage.py` — boto3 client, `S3_CACHE_BUCKET` env. Default in prod.
- [ ] Backend selection via `STORAGE_BACKEND=local|s3` env.
- [ ] `app/services/doc_cache_service.py` — `compute_document_id(file_path) -> sha256_hex` (8KB chunked read), `get(doc_id) -> CachedDoc | None` (loads chunks.json + embeddings.npy + metadata.json), `put(doc_id, chunks, embeddings, metadata)`.
- [ ] `app/api/upload.py` — extend the upload pipeline: hash → check cache → either load + re-upsert OR parse + chunk + embed + upsert + cache. Response includes `cache_hit: bool` and `chunks_indexed: int`.
- [ ] Embeddings cached in `embeddings.npy` (NumPy `.npy` format); chunks in `chunks.json`; metadata (filename, timestamp, chunk count) in `metadata.json`.
- [ ] Unit tests: `tests/unit/storage/test_local_storage.py`, `test_s3_storage.py` (use moto for S3 mock) — put/get/exists/delete roundtrip.
- [ ] Unit tests: `tests/unit/services/test_doc_cache_service.py` — hash determinism (same file → same id), get-after-put roundtrip.
- [ ] Integration test: upload `refund-policy.pdf`, then upload it again under a different filename → second response has `cache_hit=true` and returns in <1s.
- [ ] Integration test: upload, query, delete cache key, upload again — no false cache hit.

## Blocked by

- Blocked by #5 (upload pipeline exists)

## User stories addressed

- 39 (SHA-256 dedup; full L5 behavior here)

## Phase tag

`[phase-4]`.
