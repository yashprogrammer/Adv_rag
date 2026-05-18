"""Unit tests for CRAG service."""

import json
from unittest.mock import MagicMock, patch

from app.models import CRAGEvaluation, RetrievedChunk
from app.services.crag import (
    crag_pipeline,
    grade_chunks,
    should_trigger_web_search,
)


class TestGradeChunks:
    @patch("app.services.crag.generate_with_json")
    def test_returns_evaluation(self, mock_generate: MagicMock) -> None:
        mock_generate.return_value = {
            "text": json.dumps(
                {
                    "relevance_score": 0.85,
                    "relevance_label": "highly_relevant",
                    "confidence": 0.92,
                    "reasoning": "Directly answers the question.",
                }
            ),
            "usage": {},
        }
        chunks = [RetrievedChunk(text="chunk 1", source="s1", score=0.8)]

        result = grade_chunks("What is the policy?", chunks)

        assert result.relevance_score == 0.85
        assert result.relevance_label == "highly_relevant"
        assert result.confidence == 0.92
        assert result.reasoning == "Directly answers the question."
        mock_generate.assert_called_once()
        _, kwargs = mock_generate.call_args
        assert kwargs["model"] == "gpt-4o-mini"
        assert kwargs["temperature"] == 0.0

    @patch("app.services.crag.generate_with_json")
    def test_handles_grading_error(self, mock_generate: MagicMock) -> None:
        mock_generate.side_effect = RuntimeError("LLM error")
        chunks = [RetrievedChunk(text="chunk 1", source="s1", score=0.8)]

        result = grade_chunks("What is the policy?", chunks)

        assert result.relevance_score == 0.0
        assert result.relevance_label == "error"
        assert result.confidence == 0.0
        assert result.reasoning == "Grading failed"

    @patch("app.services.crag.generate_with_json")
    def test_formats_empty_chunks(self, mock_generate: MagicMock) -> None:
        mock_generate.return_value = {
            "text": json.dumps(
                {
                    "relevance_score": 0.0,
                    "relevance_label": "irrelevant",
                    "confidence": 1.0,
                    "reasoning": "No docs",
                }
            ),
            "usage": {},
        }

        result = grade_chunks("What is the policy?", [])

        assert result.relevance_label == "irrelevant"
        _, kwargs = mock_generate.call_args
        assert "No documents retrieved" in kwargs["user_message"]


class TestShouldTriggerWebSearch:
    def test_true_for_low_score(self) -> None:
        evaluation = CRAGEvaluation(
            relevance_score=0.3,
            relevance_label="irrelevant",
            confidence=0.8,
            reasoning="Low score",
        )
        assert should_trigger_web_search(evaluation) is True

    def test_false_for_high_score(self) -> None:
        evaluation = CRAGEvaluation(
            relevance_score=0.8,
            relevance_label="highly_relevant",
            confidence=0.9,
            reasoning="High score",
        )
        assert should_trigger_web_search(evaluation) is False

    def test_false_for_ambiguous(self) -> None:
        evaluation = CRAGEvaluation(
            relevance_score=0.4,
            relevance_label="ambiguous",
            confidence=0.6,
            reasoning="Ambiguous",
        )
        assert should_trigger_web_search(evaluation) is False

    def test_true_for_somewhat_relevant_below_threshold(self) -> None:
        evaluation = CRAGEvaluation(
            relevance_score=0.6,
            relevance_label="somewhat_relevant",
            confidence=0.7,
            reasoning="Below threshold",
        )
        assert should_trigger_web_search(evaluation) is True


class TestCragPipeline:
    def test_returns_original_chunks_when_disabled(self) -> None:
        chunks = [RetrievedChunk(text="chunk 1", source="s1", score=0.8)]
        final_chunks, evaluation, used_web = crag_pipeline(
            "question", chunks, enable_crag=False
        )

        assert final_chunks == chunks
        assert evaluation.relevance_label == "skipped"
        assert evaluation.relevance_score == 1.0
        assert used_web is False

    @patch("app.services.crag.search_web")
    @patch("app.services.crag.grade_chunks")
    def test_triggers_web_search_on_irrelevant(
        self, mock_grade: MagicMock, mock_search_web: MagicMock
    ) -> None:
        mock_grade.return_value = CRAGEvaluation(
            relevance_score=0.2,
            relevance_label="irrelevant",
            confidence=0.8,
            reasoning="Not relevant",
        )
        web_results = [RetrievedChunk(text="web result", source="https://example.com", score=0.9)]
        mock_search_web.return_value = web_results
        chunks = [RetrievedChunk(text="chunk 1", source="s1", score=0.1)]

        final_chunks, evaluation, used_web = crag_pipeline("question", chunks)

        assert final_chunks == web_results
        assert evaluation.relevance_label == "irrelevant"
        assert used_web is True
        mock_search_web.assert_called_once_with("question")

    @patch("app.services.crag.grade_chunks")
    def test_returns_original_chunks_on_ambiguous(self, mock_grade: MagicMock) -> None:
        mock_grade.return_value = CRAGEvaluation(
            relevance_score=0.4,
            relevance_label="ambiguous",
            confidence=0.6,
            reasoning="Unclear",
        )
        chunks = [RetrievedChunk(text="chunk 1", source="s1", score=0.5)]

        final_chunks, evaluation, used_web = crag_pipeline("question", chunks)

        assert final_chunks == chunks
        assert evaluation.relevance_label == "ambiguous"
        assert used_web is False

    @patch("app.services.crag.grade_chunks")
    def test_returns_original_chunks_on_score_between_thresholds(
        self, mock_grade: MagicMock
    ) -> None:
        mock_grade.return_value = CRAGEvaluation(
            relevance_score=0.6,
            relevance_label="ambiguous",
            confidence=0.7,
            reasoning="In range",
        )
        chunks = [RetrievedChunk(text="chunk 1", source="s1", score=0.5)]

        final_chunks, evaluation, used_web = crag_pipeline("question", chunks)

        assert final_chunks == chunks
        assert evaluation.relevance_score == 0.6
        assert used_web is False

    @patch("app.services.crag.search_web")
    @patch("app.services.crag.grade_chunks")
    def test_handles_grading_error_gracefully(
        self, mock_grade: MagicMock, mock_search_web: MagicMock
    ) -> None:
        mock_grade.return_value = CRAGEvaluation(
            relevance_score=0.0,
            relevance_label="error",
            confidence=0.0,
            reasoning="Grading failed",
        )
        mock_search_web.return_value = []
        chunks = [RetrievedChunk(text="chunk 1", source="s1", score=0.5)]

        final_chunks, evaluation, used_web = crag_pipeline("question", chunks)

        mock_search_web.assert_called_once_with("question")
        assert used_web is True
        assert evaluation.relevance_label == "error"

    @patch("app.services.crag.search_web")
    def test_triggers_web_search_when_no_chunks(self, mock_search_web: MagicMock) -> None:
        web_results = [RetrievedChunk(text="web result", source="https://example.com", score=0.9)]
        mock_search_web.return_value = web_results

        final_chunks, evaluation, used_web = crag_pipeline("question", [])

        assert final_chunks == web_results
        assert evaluation.relevance_label == "irrelevant"
        assert used_web is True

    @patch("app.services.crag.search_web")
    def test_handles_missing_tavily_key_when_no_chunks(
        self, mock_search_web: MagicMock
    ) -> None:
        mock_search_web.side_effect = ValueError("Tavily API key not configured")

        final_chunks, evaluation, used_web = crag_pipeline("question", [])

        assert final_chunks == []
        assert evaluation.relevance_label == "irrelevant"
        assert used_web is False

    @patch("app.services.crag.search_web")
    @patch("app.services.crag.grade_chunks")
    def test_handles_missing_tavily_key_on_irrelevant(
        self, mock_grade: MagicMock, mock_search_web: MagicMock
    ) -> None:
        mock_grade.return_value = CRAGEvaluation(
            relevance_score=0.2,
            relevance_label="irrelevant",
            confidence=0.8,
            reasoning="Not relevant",
        )
        mock_search_web.side_effect = ValueError("Tavily API key not configured")
        chunks = [RetrievedChunk(text="chunk 1", source="s1", score=0.1)]

        final_chunks, evaluation, used_web = crag_pipeline("question", chunks)

        assert final_chunks == []
        assert evaluation.relevance_label == "irrelevant"
        assert used_web is False
