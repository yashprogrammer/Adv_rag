"""Unit tests for Tavily web search fallback."""

from unittest.mock import MagicMock, patch

import pytest

from app.models import RetrievedChunk
from app.services.web_search import search_web


class TestSearchWeb:
    @patch("app.services.web_search.settings")
    @patch("app.services.web_search.tavily.TavilyClient")
    def test_successful_search(self, mock_client_cls: MagicMock, mock_settings: MagicMock) -> None:
        mock_settings.tavily_api_key = "test-key"
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.return_value = {
            "results": [
                {
                    "content": "Result 1 content",
                    "url": "https://example.com/1",
                    "score": 0.9,
                },
                {
                    "content": "Result 2 content",
                    "url": "https://example.com/2",
                },
            ]
        }

        results = search_web("test query", max_results=3)

        assert len(results) == 2
        assert isinstance(results[0], RetrievedChunk)
        assert results[0].text == "Result 1 content"
        assert results[0].source == "https://example.com/1"
        assert results[0].score == 0.9
        assert results[1].text == "Result 2 content"
        assert results[1].source == "https://example.com/2"
        assert results[1].score == 0.0
        mock_client.search.assert_called_once_with(
            query="test query",
            max_results=3,
            search_depth="basic",
        )

    @patch("app.services.web_search.settings")
    def test_missing_api_key_raises_value_error(self, mock_settings: MagicMock) -> None:
        mock_settings.tavily_api_key = ""

        with pytest.raises(ValueError, match="Tavily API key not configured"):
            search_web("test query")

    @patch("app.services.web_search.settings")
    @patch("app.services.web_search.tavily.TavilyClient")
    def test_api_error_returns_empty_list(
        self, mock_client_cls: MagicMock, mock_settings: MagicMock
    ) -> None:
        mock_settings.tavily_api_key = "test-key"
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.side_effect = RuntimeError("API down")

        results = search_web("test query")

        assert results == []
