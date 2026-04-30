"""L2: llm-guard input guard — prompt injection, toxicity, ban-topics scanning."""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def _load_guard() -> Any | None:
    """Try to import llm-guard scanner; return None if unavailable."""
    try:
        from llm_guard import scan_prompt
        return scan_prompt
    except Exception:
        logger.debug("llm-guard not available; input guard will use fallback")
        return None


_SCAN_PROMPT = _load_guard()


def scan_input(text: str) -> dict[str, Any]:
    """Run llm-guard scanners on input text.

    Returns dict with:
        - is_safe: bool
        - failed_checks: list[str]
        - scores: dict[str, float]
        - sanitized: str
    """
    if _SCAN_PROMPT is None:
        return {
            "is_safe": True,
            "failed_checks": [],
            "scores": {},
            "sanitized": text,
        }

    try:
        result = _SCAN_PROMPT(
            text,
            scanners=["PromptInjection", "Toxicity", "BanTopics", "TokenLimit"],
            threshold=settings.prompt_injection_threshold,
        )
        return {
            "is_safe": bool(result.get("is_safe", True)),
            "failed_checks": list(result.get("failed_checks", [])),
            "scores": dict(result.get("scores", {})),
            "sanitized": str(result.get("sanitized", text)),
        }
    except Exception:
        logger.exception("llm-guard scan failed; allowing input")
        return {
            "is_safe": True,
            "failed_checks": [],
            "scores": {},
            "sanitized": text,
        }


def check_input_safe(text: str) -> tuple[bool, str | None]:
    """Return (allowed, reason) for input text.

    If blocked, reason explains which check failed.
    """
    result = scan_input(text)
    if result["is_safe"]:
        return True, None

    checks = ", ".join(result["failed_checks"]) if result["failed_checks"] else "security scan"
    return False, f"Input blocked by {checks}"
