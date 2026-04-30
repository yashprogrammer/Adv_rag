"""Lightweight evaluation harness for local RAG pipeline."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.rag_service import run_rag


@dataclass
class EvalQuestion:
    id: str
    question: str
    expected_keywords: list[str]


def load_questions(path: Path) -> list[EvalQuestion]:
    """Load evaluation questions from JSONL file."""
    questions: list[EvalQuestion] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            try:
                qid = str(payload["id"])
                question = str(payload["question"])
                expected_keywords = [str(k) for k in payload["expected_keywords"]]
            except (KeyError, TypeError) as exc:
                raise ValueError(f"Invalid question schema at line {line_no}") from exc

            questions.append(
                EvalQuestion(
                    id=qid,
                    question=question,
                    expected_keywords=expected_keywords,
                )
            )
    return questions


def _extract_answer_and_confidence(result: Any) -> tuple[str, float]:
    if isinstance(result, dict):
        answer = str(result.get("answer", ""))
        confidence = float(result.get("confidence", 0.0) or 0.0)
        return answer, confidence

    answer = str(getattr(result, "answer", ""))
    confidence = float(getattr(result, "confidence", 0.0) or 0.0)
    return answer, confidence


def _keyword_ratio(answer: str, expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 0.0
    answer_norm = answer.lower()
    matched = sum(1 for keyword in expected_keywords if keyword.lower() in answer_norm)
    return matched / len(expected_keywords)


def evaluate_questions(questions: list[EvalQuestion]) -> dict[str, Any]:
    """Evaluate questions using the local pipeline and return aggregate metrics."""
    keyword_ratios: list[float] = []
    confidences: list[float] = []
    errors = 0

    safe_flags = {
        "top_k": 5,
        "search_mode": "dense",
        "enable_hyde": False,
        "enable_rerank": True,
        "enable_crag": False,
        "enable_self_reflective": False,
    }

    for sample in questions:
        try:
            result = run_rag(sample.question, flags=safe_flags)
            answer, confidence = _extract_answer_and_confidence(result)
            keyword_ratios.append(_keyword_ratio(answer, sample.expected_keywords))
            confidences.append(confidence)
        except Exception:
            errors += 1

    total_samples = len(questions)
    successful = total_samples - errors
    keyword_hit_rate = sum(keyword_ratios) / total_samples if total_samples else 0.0
    avg_confidence = sum(confidences) / successful if successful else 0.0

    return {
        "keyword_hit_rate": round(keyword_hit_rate, 4),
        "avg_confidence": round(avg_confidence, 4),
        "total_samples": total_samples,
        "successful_samples": successful,
        "failed_samples": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local evaluation harness")
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path("data/eval/questions.jsonl"),
        help="Path to JSONL questions file",
    )
    args = parser.parse_args()

    questions = load_questions(args.questions)
    summary = evaluate_questions(questions)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
