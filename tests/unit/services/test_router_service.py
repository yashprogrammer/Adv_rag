"""Unit tests for the LLM-based intent router service."""

from unittest.mock import MagicMock, patch

from app.services.router_service import classify_intent


class TestClassifyIntent:
    @patch("app.services.router_service.generate_with_json")
    def test_classify_intent_sql(self, mock_generate: MagicMock) -> None:
        mock_generate.return_value = {"text": '{"intent": "sql"}', "usage": {}}
        result = classify_intent("How many customers ordered last month?")
        assert result == "sql"
        mock_generate.assert_called_once()
        args, kwargs = mock_generate.call_args
        assert kwargs["model"] == "gpt-4o-mini"
        assert kwargs["temperature"] == 0.0

    @patch("app.services.router_service.generate_with_json")
    def test_classify_intent_rag(self, mock_generate: MagicMock) -> None:
        mock_generate.return_value = {"text": '{"intent": "rag"}', "usage": {}}
        result = classify_intent("What is the return policy?")
        assert result == "rag"

    @patch("app.services.router_service.generate_with_json")
    def test_classify_intent_hybrid(self, mock_generate: MagicMock) -> None:
        mock_generate.return_value = {"text": '{"intent": "hybrid"}', "usage": {}}
        result = classify_intent("How many returns last month and what is the policy?")
        assert result == "hybrid"

    @patch("app.services.router_service.generate_with_json")
    def test_fallback_on_invalid_intent(self, mock_generate: MagicMock) -> None:
        mock_generate.return_value = {"text": '{"intent": "unknown"}', "usage": {}}
        result = classify_intent("Some random question")
        assert result == "rag"

    @patch("app.services.router_service.generate_with_json")
    def test_fallback_on_exception(self, mock_generate: MagicMock) -> None:
        mock_generate.side_effect = RuntimeError("LLM service unavailable")
        result = classify_intent("Another question")
        assert result == "rag"

    @patch("app.services.router_service.generate_with_json")
    def test_fallback_on_malformed_json(self, mock_generate: MagicMock) -> None:
        mock_generate.return_value = {"text": "not json at all", "usage": {}}
        result = classify_intent("Yet another question")
        assert result == "rag"
