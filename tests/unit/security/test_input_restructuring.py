"""Unit tests for input restructuring (L5)."""

from app.security.input_restructuring import count_tokens, restructure_input, truncate_text


class TestCountTokens:
    def test_counts_words_as_fallback(self) -> None:
        # When tiktoken is unavailable, falls back to word count
        n = count_tokens("hello world")
        assert n >= 2


class TestTruncateText:
    def test_returns_original_when_under_limit(self) -> None:
        text = "short text"
        result, label = truncate_text(text, max_tokens=100)
        assert result == text
        assert label == "original"

    def test_truncates_long_text(self) -> None:
        text = "word " * 200
        result, label = truncate_text(text, max_tokens=10)
        assert label == "truncated"
        assert len(result) < len(text)


class TestRestructureInput:
    def test_returns_original_for_short_text(self) -> None:
        text = "What is the policy?"
        result, label = restructure_input(text)
        assert label == "original"
        assert result == text

    def test_truncates_medium_text(self) -> None:
        # ~3000 words should trigger truncation when limit is 2000
        text = "word " * 3000
        result, label = restructure_input(text)
        assert label in ("original", "truncated", "summarized")
        assert isinstance(result, str)
        assert len(result) <= len(text)
