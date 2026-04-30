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
    ensure_collection()

    # qdrant-client changed dense search API from `search` to `query_points`
    # in newer versions. Support both to stay compatible across environments.
    if hasattr(client, "query_points"):
        query_result = client.query_points(
            collection_name=settings.qdrant_collection,
            query=query_embedding,
            limit=top_k,
            with_payload=True,
        )
        results = query_result.points
    else:
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


def hybrid_search(
    query_embedding: list[float],
    query_text: str,
    top_k: int = 5,
    rrf_k: int = 60,
    sparse_top_k: int = 20,
) -> list[RetrievedChunk]:
    """Hybrid search: dense (Qdrant) + sparse (TF-IDF) fused with RRF.

    1. Get dense results from Qdrant
    2. Build sparse index from all Qdrant points (scroll collection)
    3. Get sparse results from TF-IDF
    4. Fuse with RRF: score = sum(1 / (rrf_k + rank)) for each result set
    5. Return top_k fused results sorted by RRF score
    """
    from app.services.sparse_vector_service import SparseVectorIndex, fuse_rrf

    # 1. Dense results
    dense_results = search(query_embedding, top_k=sparse_top_k)

    # 2. Scroll all points
    client = get_client()
    all_points, _next_page = client.scroll(
        collection_name=settings.qdrant_collection,
        limit=10000,
        with_payload=True,
        with_vectors=False,
    )

    # 3. Build sparse index
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

    # 4. Sparse results
    sparse_results = sparse_index.search(query_text, top_k=sparse_top_k)

    # 5. Fuse and return top_k
    fused = fuse_rrf([dense_results, sparse_results], rrf_k=rrf_k)
    return fused[:top_k]
