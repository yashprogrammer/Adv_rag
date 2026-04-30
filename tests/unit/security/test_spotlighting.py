"""Unit tests for spotlighting wrapper."""

from app.models import RetrievedChunk
from app.security.spotlighting import build_spotlighted_context


def test_empty_chunks_returns_empty_wrap() -> None:
    result = build_spotlighted_context([])
    assert "<retrieved_context>" in result
    assert "</retrieved_context>" in result
    assert "SECURITY NOTICE" in result


def test_chunks_wrapped_with_xml_tags() -> None:
    chunks = [
        RetrievedChunk(text="Refund within 30 days.", source="refund-policy.pdf", score=0.9),
        RetrievedChunk(text="Free shipping over $50.", source="shipping-policy.pdf", score=0.8),
    ]
    result = build_spotlighted_context(chunks)
    assert "<retrieved_context>" in result
    assert "</retrieved_context>" in result
    assert "chunk id=\"0\"" in result
    assert "chunk id=\"1\"" in result
    assert "source=\"refund-policy.pdf\"" in result
    assert "Refund within 30 days." in result
    assert "Free shipping over $50." in result


def test_security_notice_present() -> None:
    result = build_spotlighted_context([])
    assert "data not instructions" in result.lower() or "untrusted data" in result.lower()
