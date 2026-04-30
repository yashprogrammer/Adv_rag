"""Unit tests for HyDE retriever."""

from unittest.mock import MagicMock, patch

from app.models import RetrievedChunk
from app.services.hyde import HyDERetriever


class TestHyDERetriever:
    @patch("app.services.hyde.generate")
    @patch("app.services.hyde.embed_texts")
    @patch("app.services.hyde.search")
    def test_retrieve_generates_correct_number_of_hypotheses(
        self,
        mock_search: MagicMock,
        mock_embed_texts: MagicMock,
        mock_generate: MagicMock,
    ) -> None:
        mock_generate.side_effect = [
            {"text": f"hypothesis {i}", "usage": {}} for i in range(3)
        ]
        mock_embed_texts.return_value = [[0.1], [0.2], [0.3], [0.4]]
        mock_search.return_value = [
            RetrievedChunk(text="chunk", source="src", score=0.5)
        ]

        retriever = HyDERetriever(num_hypotheses=3)
        results = retriever.retrieve("what is the return policy?", top_k=5)

        assert mock_generate.call_count == 3
        assert mock_embed_texts.call_count == 1
        assert len(results) == 1
        assert results[0].text == "chunk"

    @patch("app.services.hyde.generate")
    @patch("app.services.hyde.embed_texts")
    @patch("app.services.hyde.search")
    def test_deduplication_keeps_highest_score(
        self,
        mock_search: MagicMock,
        mock_embed_texts: MagicMock,
        mock_generate: MagicMock,
    ) -> None:
        mock_generate.side_effect = [
            {"text": "hypothesis 1", "usage": {}},
            {"text": "hypothesis 2", "usage": {}},
        ]
        mock_embed_texts.return_value = [[0.1], [0.2], [0.3], [0.4]]

        def _search_side_effect(embedding, top_k=5):
            if embedding == [0.1]:
                return [RetrievedChunk(text="chunk a", source="s1", score=0.5)]
            if embedding == [0.2]:
                return [RetrievedChunk(text="chunk a", source="s1", score=0.9)]
            if embedding == [0.3]:
                return [RetrievedChunk(text="chunk b", source="s2", score=0.7)]
            return []

        mock_search.side_effect = _search_side_effect

        retriever = HyDERetriever(num_hypotheses=2)
        results = retriever.retrieve("question", top_k=5)

        assert len(results) == 2
        texts = [r.text for r in results]
        assert "chunk a" in texts
        assert "chunk b" in texts

        chunk_a = next(r for r in results if r.text == "chunk a")
        assert chunk_a.score == 0.9

        assert results[0].score >= results[1].score

    @patch("app.services.hyde.generate")
    @patch("app.services.hyde.embed_texts")
    @patch("app.services.hyde.search")
    def test_fallback_when_all_hypotheses_fail(
        self,
        mock_search: MagicMock,
        mock_embed_texts: MagicMock,
        mock_generate: MagicMock,
    ) -> None:
        mock_generate.side_effect = Exception("LLM error")
        mock_embed_texts.return_value = [[0.9]]
        mock_search.return_value = [
            RetrievedChunk(text="fallback chunk", source="src", score=0.6)
        ]

        retriever = HyDERetriever(num_hypotheses=3)
        results = retriever.retrieve("question", top_k=5)

        assert mock_generate.call_count == 3
        mock_embed_texts.assert_called_once()
        mock_search.assert_called_once()
        assert len(results) == 1
        assert results[0].text == "fallback chunk"

    def test_empty_question_returns_empty_list(self) -> None:
        retriever = HyDERetriever(num_hypotheses=3)
        assert retriever.retrieve("") == []
        assert retriever.retrieve("   ") == []

    @patch("app.services.hyde.generate")
    @patch("app.services.hyde.embed_texts")
    @patch("app.services.hyde.search")
    def test_results_limited_to_top_k(
        self,
        mock_search: MagicMock,
        mock_embed_texts: MagicMock,
        mock_generate: MagicMock,
    ) -> None:
        mock_generate.return_value = {"text": "hypothesis", "usage": {}}
        mock_embed_texts.return_value = [[0.1], [0.2]]
        mock_search.return_value = [
            RetrievedChunk(text=f"chunk {i}", source="src", score=0.1 * i)
            for i in range(1, 10)
        ]

        retriever = HyDERetriever(num_hypotheses=1)
        results = retriever.retrieve("question", top_k=3)

        assert len(results) == 3
        assert results[0].score >= results[1].score >= results[2].score

    @patch("app.services.hyde.generate")
    @patch("app.services.hyde.embed_texts")
    @patch("app.services.hyde.search")
    def test_whitespace_normalization_for_dedup(
        self,
        mock_search: MagicMock,
        mock_embed_texts: MagicMock,
        mock_generate: MagicMock,
    ) -> None:
        mock_generate.return_value = {"text": "hypothesis", "usage": {}}
        mock_embed_texts.return_value = [[0.1], [0.2]]
        mock_search.side_effect = [
            [RetrievedChunk(text="chunk  a", source="s1", score=0.5)],
            [RetrievedChunk(text="chunk a", source="s1", score=0.8)],
        ]

        retriever = HyDERetriever(num_hypotheses=1)
        results = retriever.retrieve("question", top_k=5)

        assert len(results) == 1
        assert results[0].score == 0.8
