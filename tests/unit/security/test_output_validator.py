"""Unit tests for output schema validation with retry."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.security.output_validator import validate_with_retry


def test_valid_json_passes_first_try() -> None:
    raw = '{"answer": "ok", "sources": ["a.pdf"], "confidence": 0.8}'
    result = validate_with_retry(raw, llm_fn=MagicMock(), max_retries=2)
    assert result.answer == "ok"
    assert result.confidence == 0.8


def test_invalid_json_triggers_retry_and_succeeds() -> None:
    raw = '{"answer": "ok", "sources": ["a.pdf"], "confidence": 1.5}'  # confidence > 1

    def fixed_llm_fn(prompt: str, error: str) -> str:
        return '{"answer": "fixed", "sources": ["b.pdf"], "confidence": 0.9}'

    result = validate_with_retry(raw, llm_fn=fixed_llm_fn, max_retries=2)
    assert result.answer == "fixed"
    assert result.confidence == 0.9


def test_invalid_json_exhausts_retries_and_raises() -> None:
    raw = '{"answer": "ok", "confidence": 1.5}'  # missing sources, bad confidence

    def bad_llm_fn(prompt: str, error: str) -> str:
        return raw

    with pytest.raises(ValidationError):
        validate_with_retry(raw, llm_fn=bad_llm_fn, max_retries=2)


def test_markdown_fences_stripped_before_parsing() -> None:
    raw = '```json\n{"answer": "ok", "sources": [], "confidence": 0.5}\n```'
    result = validate_with_retry(raw, llm_fn=MagicMock(), max_retries=2)
    assert result.answer == "ok"
