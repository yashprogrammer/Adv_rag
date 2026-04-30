"""Unit tests for vector store hybrid search."""

from unittest.mock import MagicMock, patch

from app.models import RetrievedChunk
from app.services.vector_store import hybrid_search


def test_hybrid_search_fuses_dense_and_sparse() -> None:
    dense_results = [
        RetrievedChunk(text="doc a", source="s1", score=0.9),
        RetrievedChunk(text="doc b", source="s1", score=0.8),
    ]

    mock_point1 = MagicMock()
    mock_point1.id = "p1"
    mock_point1.payload = {"text": "doc a", "source": "s1"}
    mock_point2 = MagicMock()
    mock_point2.id = "p2"
    mock_point2.payload = {"text": "doc b", "source": "s1"}
    mock_point3 = MagicMock()
    mock_point3.id = "p3"
    mock_point3.payload = {"text": "doc c", "source": "s2"}

    scroll_return = ([mock_point1, mock_point2, mock_point3], None)

    with patch("app.services.vector_store.search", return_value=dense_results):
        with patch("app.services.vector_store.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.scroll.return_value = scroll_return
            mock_get_client.return_value = mock_client

            with patch(
                "app.services.sparse_vector_service.SparseVectorIndex"
            ) as mock_sparse_cls:
                mock_sparse_instance = MagicMock()
                mock_sparse_instance.search.return_value = [
                    RetrievedChunk(text="doc b", source="s1", score=0.85),
                    RetrievedChunk(text="doc c", source="s2", score=0.75),
                ]
                mock_sparse_cls.return_value = mock_sparse_instance

                results = hybrid_search(
                    query_embedding=[0.1] * 1536,
                    query_text="query",
                    top_k=2,
                    rrf_k=60,
                    sparse_top_k=20,
                )

    assert len(results) == 2
    # doc b: dense rank 2 (1/62) + sparse rank 1 (1/61) => highest RRF
    assert results[0].text == "doc b"
    # doc a: dense rank 1 (1/61) only => second highest
    assert results[1].text == "doc a"
