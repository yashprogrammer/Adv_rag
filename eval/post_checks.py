"""Non-Ragas post-check assertions per golden."""

from __future__ import annotations


def forbidden_keywords_check(answer: str, forbidden: list[str]) -> dict:
    """Check that the answer does NOT contain any forbidden keywords.

    Args:
        answer: The generated answer text.
        forbidden: List of forbidden substrings (case-insensitive).

    Returns:
        Dict with ``passed`` (bool) and ``hits`` (list of matched keywords).
    """
    answer_lower = answer.lower()
    hits = [kw for kw in forbidden if kw.lower() in answer_lower]
    return {"passed": not hits, "hits": hits}


def source_overlap(actual: list[str], golden: list[str]) -> dict:
    """Compute source overlap between actual and golden source lists.

    Args:
        actual: Sources returned by the pipeline.
        golden: Expected sources from the golden entry.

    Returns:
        Dict with ``overlap_pct``, ``matched``, and ``missed``.
    """
    import os

    def _norm(s: str) -> str:
        return os.path.splitext(os.path.basename(s.strip().lower()))[0]

    actual_set = {_norm(s) for s in actual}
    golden_set = {_norm(s) for s in golden}
    overlap = actual_set & golden_set
    return {
        "overlap_pct": round(len(overlap) / max(len(golden_set), 1), 3),
        "matched": sorted(overlap),
        "missed": sorted(golden_set - actual_set),
    }
