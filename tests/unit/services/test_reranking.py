"""Unit tests for reranking service."""

from unittest.mock import MagicMock, patch

from app.models import RetrievedChunk
from app.services.reranking import Reranker


class TestRerankerLocal:
    @patch("app.services.reranking.settings")
    def test_local_reranker_sorts_by_score(self, mock_settings: MagicMock) -> None:
        mock_settings.reranker_backend = "local"
        mock_settings.reranker_model = "cross-encoder/test"
        mock_settings.reranker_initial_top_k = 20

        reranker = Reranker()
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9, 0.5, 0.8]
        reranker._local_model = mock_model

        chunks = [
            RetrievedChunk(text="a", source="s1", score=0.1),
            RetrievedChunk(text="b", source="s2", score=0.2),
            RetrievedChunk(text="c", source="s3", score=0.3),
        ]
        result = reranker.rerank("query", chunks)

        assert len(result) == 3
        assert result[0].text == "a"  # highest score 0.9
        assert result[1].text == "c"  # score 0.8
        assert result[2].text == "b"  # score 0.5
        assert result[0].score == 0.9

    @patch("app.services.reranking.settings")
    def test_empty_chunks_returns_empty(self, mock_settings: MagicMock) -> None:
        mock_settings.reranker_backend = "local"
        mock_settings.reranker_initial_top_k = 20
        reranker = Reranker()
        assert reranker.rerank("query", []) == []

    @patch("app.services.reranking.settings")
    def test_top_k_limits_results(self, mock_settings: MagicMock) -> None:
        mock_settings.reranker_backend = "local"
        mock_settings.reranker_model = "cross-encoder/test"
        mock_settings.reranker_initial_top_k = 20

        reranker = Reranker()
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9, 0.5, 0.8]
        reranker._local_model = mock_model

        chunks = [
            RetrievedChunk(text="a", source="s1", score=0.1),
            RetrievedChunk(text="b", source="s2", score=0.2),
            RetrievedChunk(text="c", source="s3", score=0.3),
        ]
        result = reranker.rerank("query", chunks, top_k=2)
        assert len(result) == 2
        assert result[0].text == "a"
        assert result[1].text == "c"

    @patch("app.services.reranking.settings")
    def test_exception_falls_back_to_original_order(self, mock_settings: MagicMock) -> None:
        mock_settings.reranker_backend = "local"
        mock_settings.reranker_model = "cross-encoder/test"
        mock_settings.reranker_initial_top_k = 20

        reranker = Reranker()
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("model failure")
        reranker._local_model = mock_model

        chunks = [
            RetrievedChunk(text="a", source="s1", score=0.1),
            RetrievedChunk(text="b", source="s2", score=0.2),
        ]
        result = reranker.rerank("query", chunks)
        assert len(result) == 2
        assert result[0].text == "a"
        assert result[1].text == "b"


class TestRerankerVoyage:
    @patch("app.services.reranking.settings")
    def test_voyage_reranker_maps_results(self, mock_settings: MagicMock) -> None:
        mock_settings.reranker_backend = "voyage"
        mock_settings.voyage_api_key = "test-key"
        mock_settings.voyage_model = "rerank-2.5"
        mock_settings.reranker_initial_top_k = 20

        reranker = Reranker()
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.results = [
            MagicMock(index=1, relevance_score=0.95),
            MagicMock(index=0, relevance_score=0.85),
        ]
        mock_client.rerank.return_value = mock_result
        reranker._voyage_client = mock_client

        chunks = [
            RetrievedChunk(text="a", source="s1", score=0.1),
            RetrievedChunk(text="b", source="s2", score=0.2),
        ]
        result = reranker.rerank("query", chunks)

        assert len(result) == 2
        assert result[0].text == "b"
        assert result[0].score == 0.95
        assert result[1].text == "a"
        assert result[1].score == 0.85

    @patch("app.services.reranking.settings")
    def test_voyage_missing_api_key_raises(self, mock_settings: MagicMock) -> None:
        mock_settings.reranker_backend = "voyage"
        mock_settings.voyage_api_key = ""
        mock_settings.voyage_model = "rerank-2.5"
        mock_settings.reranker_initial_top_k = 20

        reranker = Reranker()
        chunks = [RetrievedChunk(text="a", source="s1", score=0.1)]
        result = reranker.rerank("query", chunks)
        # Should fall back to original order due to exception handler
        assert len(result) == 1
        assert result[0].text == "a"
