"""Unit tests for LLM service wrapper."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.llm_service import generate, generate_with_json


class TestGenerate:
    @patch("app.services.llm_service.openai_client")
    def test_generate_returns_text_and_usage(self, mock_client: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="hello"))]
        mock_response.usage = MagicMock(prompt_tokens=5, completion_tokens=2)
        mock_client.chat.completions.create.return_value = mock_response

        result = generate("system prompt", "user message")
        assert result["text"] == "hello"
        assert result["usage"]["prompt_tokens"] == 5
        assert result["usage"]["completion_tokens"] == 2

    @patch("app.services.llm_service.openai_client")
    def test_generate_with_json_returns_parsed_response(self, mock_client: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"answer": "ok"}'))]
        mock_response.usage = MagicMock(prompt_tokens=3, completion_tokens=4)
        mock_client.chat.completions.create.return_value = mock_response

        result = generate_with_json("system", "user")
        assert result["text"] == '{"answer": "ok"}'


class TestLLMServiceErrorHandling:
    @patch("app.services.llm_service.openai_client")
    def test_generate_raises_on_api_error(self, mock_client: MagicMock) -> None:
        from openai import APIError

        mock_client.chat.completions.create.side_effect = APIError(
            message="bad", request=MagicMock(), body=None
        )
        with pytest.raises(APIError):
            generate("system", "user")
