"""L7: Content moderation + PII redaction for input and output."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Fallback regex-based PII patterns when llm-guard Sensitive is unavailable
_PII_PATTERNS: list[tuple[str, str]] = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[REDACTED_EMAIL]"),
    (r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "[REDACTED_PHONE]"),
    (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[REDACTED_CARD]"),
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[REDACTED_IP]"),
]


def _load_moderation() -> Any | None:
    try:
        from llm_guard import scan_output
        return scan_output
    except Exception:
        logger.debug("llm-guard output scan not available; using fallback")
        return None


from typing import Any

_SCAN_OUTPUT = _load_moderation()


def redact_pii(text: str) -> str:
    """Redact common PII patterns from text.

    Uses llm-guard Sensitive if available, otherwise regex fallback.
    """
    if _SCAN_OUTPUT is not None:
        try:
            result = _SCAN_OUTPUT(
                text,
                scanners=["Sensitive"],
                threshold=settings.output_toxicity_threshold,
            )
            return str(result.get("sanitized", text))
        except Exception:
            logger.exception("llm-guard PII redaction failed; using regex fallback")

    for pattern, replacement in _PII_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def moderate_output(text: str) -> tuple[bool, str | None]:
    """Moderate LLM output text. Returns (allowed, reason_or_none).

    If blocked, reason explains why. If allowed, text is redacted in-place.
    """
    if _SCAN_OUTPUT is not None:
        try:
            result = _SCAN_OUTPUT(
                text,
                scanners=["Toxicity", "BanTopics", "Sensitive"],
                threshold=settings.output_toxicity_threshold,
            )
            if not result.get("is_safe", True):
                checks = ", ".join(result.get("failed_checks", []))
                return False, f"Output blocked by {checks}"
            return True, None
        except Exception:
            logger.exception("llm-guard output moderation failed; allowing")

    return True, None


def moderate_and_redact(text: str) -> tuple[bool, str, str | None]:
    """Moderate output and redact PII. Returns (allowed, redacted_text, reason).

    Always redacts PII even if moderation passes.
    """
    allowed, reason = moderate_output(text)
    redacted = redact_pii(text)
    return allowed, redacted, reason
