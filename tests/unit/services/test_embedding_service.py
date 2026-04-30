"""Unit tests for embedding service."""

from unittest.mock import ANY, MagicMock, patch

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


def test_embed_texts_uses_cache_and_batches_misses() -> None:
    """Cache hit returns stored vector; miss triggers a single batched OpenAI call."""
    mock_response = MagicMock()
    mock_response.data = [
        MagicMock(embedding=[0.7, 0.8, 0.9]),
    ]

    with (
        patch("app.services.embedding_service.openai_client") as mock_client,
        patch("app.services.embedding_service.query_cache") as mock_cache,
    ):
        mock_client.embeddings.create.return_value = mock_response
        # First text is cached, second is a miss
        mock_cache.get_embedding.side_effect = [
            [0.1, 0.2, 0.3],  # "cached"
            None,             # "new"
        ]

        result = embed_texts(["cached", "new"])

        # OpenAI called only for the miss
        mock_client.embeddings.create.assert_called_once_with(input=["new"], model=ANY)
        # Cache set for the miss
        mock_cache.set_embedding.assert_called_once_with("new", [0.7, 0.8, 0.9])
        # Results preserved in original order
        assert result == [[0.1, 0.2, 0.3], [0.7, 0.8, 0.9]]


def test_embed_texts_all_hits_no_openai_call() -> None:
    """When every text is cached, OpenAI is never called."""
    with (
        patch("app.services.embedding_service.openai_client") as mock_client,
        patch("app.services.embedding_service.query_cache") as mock_cache,
    ):
        mock_cache.get_embedding.side_effect = [
            [0.1, 0.2],
            [0.3, 0.4],
        ]

        result = embed_texts(["a", "b"])

        mock_client.embeddings.create.assert_not_called()
        mock_cache.set_embedding.assert_not_called()
        assert result == [[0.1, 0.2], [0.3, 0.4]]
