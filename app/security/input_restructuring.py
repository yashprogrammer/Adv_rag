"""Input moderation and restructuring hooks with safe fallbacks."""

from __future__ import annotations

from collections.abc import Callable


def moderate_input_text(
    text: str,
    moderation_fn: Callable[[str], bool] | None = None,
) -> tuple[bool, str | None]:
    """Run moderation hook and never fail closed on provider errors."""
    if moderation_fn is None:
        return True, None

    try:
        allowed = bool(moderation_fn(text))
    except Exception:
        return True, None

    if not allowed:
        return False, "Input was blocked by moderation policy"
    return True, None


def restructure_input_text(
    text: str,
    restructuring_fn: Callable[[str], str] | None = None,
) -> str:
    """Run restructuring hook with original-text fallback."""
    if restructuring_fn is None:
        return text

    try:
        candidate = restructuring_fn(text)
    except Exception:
        return text

    if isinstance(candidate, str) and candidate:
        return candidate
    return text


def apply_input_security_pipeline(
    text: str,
    moderation_fn: Callable[[str], bool] | None = None,
    restructuring_fn: Callable[[str], str] | None = None,
) -> tuple[bool, str, str | None]:
    """Apply moderation then restructuring with graceful degradation."""
    allowed, reason = moderate_input_text(text, moderation_fn=moderation_fn)
    if not allowed:
        return False, text, reason

    return True, restructure_input_text(text, restructuring_fn=restructuring_fn), None
