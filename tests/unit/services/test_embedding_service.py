"""Unit tests for embedding service."""

from unittest.mock import MagicMock, patch

from app.services.embedding_service import embed_texts


def test_embed_texts_returns_vectors_in_order() -> None:
    mock_response = MagicMock()
    mock_response.data = [
        MagicMock(embedding=[0.1, 0.2, 0.3]),
        MagicMock(embedding=[0.4, 0.5, 0.6]),
    ]

    with patch("app.services.embedding_service.openai_client") as mock_client:
        mock_client.embeddings.create.return_value = mock_response
        result = embed_texts(["hello", "world"])

    assert len(result) == 2
    assert result[0] == [0.1, 0.2, 0.3]
    assert result[1] == [0.4, 0.5, 0.6]


def test_embed_texts_empty_list_returns_empty() -> None:
    result = embed_texts([])
    assert result == []
