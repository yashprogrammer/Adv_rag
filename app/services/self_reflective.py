"""Self-RAG: reflect on generated answer quality and decide if regeneration is needed."""

import json
import logging

from app.config import settings
from app.models import ReflectionResult
from app.services.llm_service import generate_with_json

_REFLECTION_PROMPT = """You are evaluating the quality of an AI-generated answer to a user question.

User Question: {question}

Generated Answer: {answer}

Retrieved Context (if any): {context}

Evaluate the answer on these criteria (1-10 scale each):
1. Relevance: Does the answer directly address the question?
2. Accuracy: Is the information factually correct based on the context?
3. Completeness: Does the answer cover all aspects of the question?
4. Clarity: Is the answer clear and well-structured?

Overall reflection score = average of the four criteria / 10.0 (scale 0.0-1.0)

If the score is below 0.8, the answer needs regeneration. Provide a refined version of the question that would help generate a better answer.

Respond ONLY with a JSON object:
{{"reflection_score": float, "needs_regeneration": bool, "refined_question": str, "reasoning": str}}
"""


def reflect_on_answer(
    question: str,
    answer: str,
    context: str = "",
) -> ReflectionResult:
    """Reflect on the generated answer quality.

    Returns ReflectionResult with score and regeneration recommendation.
    On any error, returns a default result that does NOT need regeneration.
    """
    try:
        formatted_prompt = _REFLECTION_PROMPT.format(
            question=question,
            answer=answer,
            context=context,
        )
        response = generate_with_json(
            system_prompt=formatted_prompt,
            user_message="",
            model=settings.llm_model_grader,
            temperature=0.0,
        )
        parsed = json.loads(response["text"])
        return ReflectionResult(**parsed)
    except Exception as exc:
        logging.error("Reflection failed: %s", exc)
        return ReflectionResult(
            reflection_score=1.0,
            needs_regeneration=False,
            refined_question="",
            reasoning="Reflection failed, accepting answer as-is",
        )


def should_regenerate(reflection: ReflectionResult, iteration: int) -> bool:
    """Determine if answer should be regenerated based on reflection and iteration count.

    Returns True if:
    - reflection.needs_regeneration is True AND
    - reflection.reflection_score < settings.reflection_min_score AND
    - iteration < settings.max_reflection_retries

    Otherwise returns False.
    """
    return (
        reflection.needs_regeneration
        and reflection.reflection_score < settings.reflection_min_score
        and iteration < settings.max_reflection_retries
    )
