"""LLM-based intent router for classifying user questions."""

import json
import logging
from typing import Literal

from app.config import settings
from app.services.llm_service import generate_with_json

Intent = Literal["sql", "rag", "hybrid"]

_INTENT_SYSTEM_PROMPT = """You are an intent classifier for an e-commerce customer support AI.
Classify the user question into exactly one of these categories:
- "sql": Questions about numerical data, counts, totals, sums, averages, or specific facts stored in a database (e.g., "how many customers", "what is the average order value", "total revenue last month")
- "rag": Questions about policies, procedures, troubleshooting, or general knowledge that would be found in documents (e.g., "what is the return policy", "how do I reset my password", "shipping timeframes")
- "hybrid": Questions that mix both numerical data and policy/knowledge (e.g., "how many customers returned items last month and what is the return policy")

Respond ONLY with a JSON object in this exact format:
{"intent": "sql"} or {"intent": "rag"} or {"intent": "hybrid"}
"""

logger = logging.getLogger(__name__)


def classify_intent(question: str) -> Intent:
    """Classify user question intent using an LLM.

    Returns one of: "sql", "rag", "hybrid"
    Falls back to "rag" if LLM fails or returns invalid intent.
    """
    try:
        response = generate_with_json(
            system_prompt=_INTENT_SYSTEM_PROMPT,
            user_message=question,
            model=settings.llm_model_grader,
            temperature=0.0,
        )
        raw_text = response.get("text", "")
        parsed = json.loads(raw_text)
        intent = parsed.get("intent", "")

        if intent in ("sql", "rag", "hybrid"):
            return intent  # type: ignore[return-value]

        logger.error("Invalid intent returned by LLM: %s", intent)
        return "rag"
    except Exception:
        logger.exception("Intent classification failed, falling back to rag")
        return "rag"
