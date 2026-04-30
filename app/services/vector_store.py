"""Qdrant vector store — dense-only search for Phase 1."""

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import settings
from app.models import RetrievedChunk

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url)
    return _client


def ensure_collection() -> None:
    client = get_client()
    if not client.collection_exists(settings.qdrant_collection):
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=1536,
                distance=Distance.COSINE,
            ),
        )


def upsert_chunks(chunks: list[RetrievedChunk], embeddings: list[list[float]]) -> None:
    """Upsert chunks with their embeddings into Qdrant."""
    ensure_collection()
    client = get_client()
    points = []
    for i, (chunk, vec) in enumerate(zip(chunks, embeddings, strict=True)):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{chunk.source}:{i}:{chunk.text[:50]}"))
        points.append(
            PointStruct(
                id=point_id,
                vector=vec,
                payload={
                    "text": chunk.text,
                    "source": chunk.source,
                },
            )
        )
    client.upsert(collection_name=settings.qdrant_collection, points=points)


def search(query_embedding: list[float], top_k: int = 5) -> list[RetrievedChunk]:
    """Search Qdrant for the top-k most similar chunks."""
    client = get_client()
    results = client.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_embedding,
        limit=top_k,
        with_payload=True,
    )
    return [
        RetrievedChunk(
            text=hit.payload.get("text", ""),
            source=hit.payload.get("source", ""),
            score=hit.score,
        )
        for hit in results
    ]
