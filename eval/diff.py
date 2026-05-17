"""Compare two eval result JSONs (Phase C)."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python -m eval.diff <prev.json> <curr.json>")
        sys.exit(1)

    prev = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    curr = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

    print(f"\n## Diff — {prev['profile']} → {curr['profile']}\n")
    print("| metric | prev | curr | Δ |")
    print("|---|---|---|---|")

    for k in (
        "faithfulness",
        "context_precision",
        "context_recall",
        "answer_relevancy",
    ):
        p = prev["aggregate"].get(k)
        c = curr["aggregate"].get(k)
        if p is None or c is None:
            continue
        print(f"| {k} | {p:.3f} | {c:.3f} | {c - p:+.3f} |")

    # Threshold gating (advisory only)
    THRESHOLDS = {
        "faithfulness": 0.85,
        "context_precision": 0.75,
        "context_recall": 0.70,
        "answer_relevancy": 0.80,
    }

    print("\n### Threshold check (advisory)\n")
    print("| metric | actual | threshold | status |")
    print("|---|---|---|---|")
    for k, threshold in THRESHOLDS.items():
        actual = curr["aggregate"].get(k)
        if actual is None:
            continue
        status = "PASS" if actual >= threshold else "FAIL"
        print(f"| {k} | {actual:.3f} | {threshold:.2f} | {status} |")


if __name__ == "__main__":
    main()
