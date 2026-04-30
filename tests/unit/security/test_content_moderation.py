"""Unit tests for content moderation + PII redaction (L7)."""

from app.security.content_moderation import moderate_and_redact, redact_pii


class TestRedactPii:
    def test_redacts_email(self) -> None:
        text = "Contact us at support@example.com for help."
        result = redact_pii(text)
        assert "[REDACTED_EMAIL]" in result
        assert "support@example.com" not in result

    def test_redacts_phone(self) -> None:
        text = "Call 1-800-555-1234 for assistance."
        result = redact_pii(text)
        assert "[REDACTED_PHONE]" in result
        assert "1-800-555-1234" not in result

    def test_redacts_credit_card(self) -> None:
        text = "Card 1234 5678 9012 3456 is on file."
        result = redact_pii(text)
        assert "[REDACTED_CARD]" in result
        assert "1234 5678 9012 3456" not in result

    def test_redacts_ip(self) -> None:
        text = "Server at 192.168.1.1 is down."
        result = redact_pii(text)
        assert "[REDACTED_IP]" in result
        assert "192.168.1.1" not in result

    def test_leaves_clean_text(self) -> None:
        text = "What is the return policy?"
        result = redact_pii(text)
        assert result == text


class TestModerateAndRedact:
    def test_returns_allowed_for_clean_text(self) -> None:
        allowed, redacted, reason = moderate_and_redact("Hello world")
        assert allowed is True
        assert reason is None
        assert redacted == "Hello world"

    def test_redacts_even_when_allowed(self) -> None:
        allowed, redacted, reason = moderate_and_redact("Email: admin@company.com")
        assert allowed is True
        assert "[REDACTED_EMAIL]" in redacted
        assert reason is None
