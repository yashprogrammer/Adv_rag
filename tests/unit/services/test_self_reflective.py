"""Unit tests for self-reflective service."""

from unittest.mock import MagicMock, patch

from app.models import ReflectionResult
from app.services.self_reflective import reflect_on_answer, should_regenerate


class TestReflectOnAnswer:
    @patch("app.services.self_reflective.generate_with_json")
    def test_returns_high_score_for_good_answer(self, mock_generate: MagicMock) -> None:
        mock_generate.return_value = {
            "text": '{"reflection_score": 0.95, "needs_regeneration": false, "refined_question": "", "reasoning": "Good answer"}',
            "usage": {},
        }
        result = reflect_on_answer("question", "answer", "context")
        assert result.reflection_score == 0.95
        assert result.needs_regeneration is False
        assert result.refined_question == ""
        assert result.reasoning == "Good answer"

    @patch("app.services.self_reflective.generate_with_json")
    def test_returns_needs_regeneration_for_poor_answer(self, mock_generate: MagicMock) -> None:
        mock_generate.return_value = {
            "text": '{"reflection_score": 0.5, "needs_regeneration": true, "refined_question": "refined", "reasoning": "Poor answer"}',
            "usage": {},
        }
        result = reflect_on_answer("question", "answer", "context")
        assert result.reflection_score == 0.5
        assert result.needs_regeneration is True
        assert result.refined_question == "refined"
        assert result.reasoning == "Poor answer"

    @patch("app.services.self_reflective.generate_with_json")
    def test_includes_refined_question_when_regeneration_needed(self, mock_generate: MagicMock) -> None:
        mock_generate.return_value = {
            "text": '{"reflection_score": 0.3, "needs_regeneration": true, "refined_question": "better question", "reasoning": "Missing details"}',
            "usage": {},
        }
        result = reflect_on_answer("q", "a")
        assert result.refined_question == "better question"
        assert result.needs_regeneration is True

    @patch("app.services.self_reflective.generate_with_json")
    def test_falls_back_gracefully_on_llm_error(self, mock_generate: MagicMock) -> None:
        mock_generate.side_effect = Exception("LLM error")
        result = reflect_on_answer("q", "a")
        assert result.reflection_score == 1.0
        assert result.needs_regeneration is False
        assert result.refined_question == ""
        assert result.reasoning == "Reflection failed, accepting answer as-is"

    @patch("app.services.self_reflective.generate_with_json")
    def test_falls_back_gracefully_on_malformed_json(self, mock_generate: MagicMock) -> None:
        mock_generate.return_value = {
            "text": "not json",
            "usage": {},
        }
        result = reflect_on_answer("q", "a")
        assert result.reflection_score == 1.0
        assert result.needs_regeneration is False
        assert result.refined_question == ""
        assert result.reasoning == "Reflection failed, accepting answer as-is"


class TestShouldRegenerate:
    def test_true_when_score_below_threshold_and_iterations_available(self) -> None:
        reflection = ReflectionResult(
            reflection_score=0.5,
            needs_regeneration=True,
            refined_question="refined",
            reasoning="bad",
        )
        assert should_regenerate(reflection, iteration=0) is True

    def test_false_when_score_above_threshold(self) -> None:
        reflection = ReflectionResult(
            reflection_score=0.9,
            needs_regeneration=True,
            refined_question="refined",
            reasoning="bad",
        )
        assert should_regenerate(reflection, iteration=0) is False

    def test_false_when_max_iterations_reached(self) -> None:
        reflection = ReflectionResult(
            reflection_score=0.5,
            needs_regeneration=True,
            refined_question="refined",
            reasoning="bad",
        )
        assert should_regenerate(reflection, iteration=2) is False

    def test_false_when_reflection_says_no_regeneration_needed(self) -> None:
        reflection = ReflectionResult(
            reflection_score=0.5,
            needs_regeneration=False,
            refined_question="refined",
            reasoning="bad",
        )
        assert should_regenerate(reflection, iteration=0) is False
