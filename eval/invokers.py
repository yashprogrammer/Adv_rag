"""Abstract invokers for service-mode and API-mode evaluation.

Lesson 0 — the ServiceInvoker is a STUB. The RAG service does not exist yet.
Running `make eval-baseline` here will fail with a clear message:
  "RAG service not implemented — see Lesson 1 (lesson-1-naive branch)."

The invoker is fleshed out incrementally:
  - L1 wires run_rag_with_trace_no_cache (dense only)
  - L2+ wire additional retrieval modes via the same call site
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SkippedIntent(Exception):
    """Raised when a golden's intent cannot be handled by the current invoker."""

    pass


class Invoker(ABC):
    """Abstract base for evaluation invokers."""

    @abstractmethod
    def invoke(
        self, question: str, flags: dict, intent: str
    ) -> tuple[Any, list]:
        """Run a single golden through the pipeline."""
        ...


class ServiceInvoker(Invoker):
    """L0 STUB — raises NotImplementedError.

    In Lesson 1 this method is replaced with a real call to
    `run_rag_with_trace_no_cache` to drive the naive RAG pipeline.
    """

    SUPPORTED_INTENTS = {"rag", "web_fallback"}

    def invoke(
        self, question: str, flags: dict, intent: str
    ) -> tuple[Any, list]:
        raise NotImplementedError(
            "RAG service is not implemented in Lesson 0. "
            "Switch to the lesson-1-naive branch to enable retrieval-based evaluation."
        )
