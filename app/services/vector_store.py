"""Vector store — Lesson 2: dense + sparse + hybrid (RRF) search.

L1 had `search()` only. L2 adds:
  - sparse_search()   : pure TF-IDF (BM25-style) lexical match
  - hybrid_search()   : dense + sparse fused via Reciprocal Rank Fusion (RRF)

The hybrid leg builds an in-memory TF-IDF index from every chunk currently
in Qdrant on every query. Acceptable for the course's small corpus
(~3.5K chunks); a production system would persist the sparse index.
"""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import settings
from app.models import RetrievedChunk

VECTOR_SIZE = 1536


def get_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, timeout=30)


def ensure_collection() -> None:
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def upsert_chunks(chunks: list[RetrievedChunk], embeddings: list[list[float]]) -> None:
    ensure_collection()
    client = get_client()
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={"text": chunk.text, "source": chunk.source},
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]
    client.upsert(collection_name=settings.qdrant_collection, points=points)


def search(query_embedding: list[float], top_k: int = 5) -> list[RetrievedChunk]:
    """Dense vector search via Qdrant cosine similarity."""
    client = get_client()
    results = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_embedding,
        limit=top_k,
        with_payload=True,
    ).points

    return [
        RetrievedChunk(
            text=p.payload.get("text", ""),
            source=p.payload.get("source", ""),
            score=float(p.score),
        )
        for p in results
    ]


def _build_sparse_index():
    """Scroll Qdrant and build an in-memory TF-IDF sparse index."""
    from app.services.sparse_vector_service import SparseVectorIndex

    client = get_client()
    all_points, _next_page = client.scroll(
        collection_name=settings.qdrant_collection,
        limit=10000,
        with_payload=True,
        with_vectors=False,
    )
    documents = [
        {
            "text": point.payload.get("text", "") if point.payload else "",
            "source": point.payload.get("source", "") if point.payload else "",
            "id": str(point.id),
        }
        for point in all_points
    ]
    sparse_index = SparseVectorIndex()
    sparse_index.fit(documents)
    return sparse_index


def sparse_search(query_text: str, top_k: int = 5) -> list[RetrievedChunk]:
    """Pure sparse search using TF-IDF (no dense embeddings, no fusion)."""
    sparse_index = _build_sparse_index()
    return sparse_index.search(query_text, top_k=top_k)


def hybrid_search(
    query_embedding: list[float],
    query_text: str,
    top_k: int = 5,
    rrf_k: int = 60,
    sparse_top_k: int = 20,
) -> list[RetrievedChunk]:
    """Hybrid retrieval: dense (Qdrant) + sparse (TF-IDF), fused via RRF.

    Reciprocal Rank Fusion is rank-only — it doesn't care about the
    underlying score magnitudes, only the position each chunk has in the
    two result lists. Score = sum(1 / (rrf_k + rank)) across both lists.
    """
    from app.services.sparse_vector_service import fuse_rrf

    dense_results = search(query_embedding, top_k=sparse_top_k)
    sparse_index = _build_sparse_index()
    sparse_results = sparse_index.search(query_text, top_k=sparse_top_k)
    fused = fuse_rrf([dense_results, sparse_results], rrf_k=rrf_k)
    return fused[:top_k]
