"""Abstract invokers for service-mode and API-mode evaluation."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.config import settings
from app.models import ChatResponse, RetrievedChunk
from app.services.rag_service import run_rag_with_trace_no_cache


class SkippedIntent(Exception):
    """Raised when a golden's intent cannot be handled by the current invoker."""

    pass


class Invoker(ABC):
    """Abstract base for evaluation invokers."""

    @abstractmethod
    def invoke(
        self, question: str, flags: dict, intent: str
    ) -> tuple[ChatResponse, list[RetrievedChunk]]:
        """Run a single golden through the pipeline.

        Args:
            question: The user's question.
            flags: Flag profile dict.
            intent: Intent from the golden (rag, sql, hybrid, web_fallback).

        Returns:
            Tuple of (ChatResponse, list of RetrievedChunk).

        Raises:
            SkippedIntent: If the invoker cannot handle this intent.
        """
        ...


class ServiceInvoker(Invoker):
    """Phase A — direct in-process call.

    Lesson 7 unlocks the SQL + hybrid intents (auto-route via the intent
    classifier in run_rag_with_trace_no_cache).
    """

    SUPPORTED_INTENTS = {"rag", "web_fallback", "sql", "hybrid"}

    def invoke(
        self, question: str, flags: dict, intent: str
    ) -> tuple[ChatResponse, list[RetrievedChunk]]:
        if intent not in self.SUPPORTED_INTENTS:
            raise SkippedIntent(f"intent={intent} not supported in service mode")

        if intent == "web_fallback" and not settings.tavily_api_key:
            raise SkippedIntent("tavily_unset: TAVILY_API_KEY not configured")

        return run_rag_with_trace_no_cache(question, flags)


# Phase B will add:
# class ApiInvoker(Invoker): ...
