"""Unit tests for evaluation harness metrics and fault tolerance."""

from pathlib import Path
from unittest.mock import patch

from scripts.eval import EvalQuestion, evaluate_questions, load_questions


def test_load_questions_parses_jsonl(tmp_path: Path) -> None:
    questions_file = tmp_path / "questions.jsonl"
    questions_file.write_text(
        '{"id":"q1","question":"What is RAG?","expected_keywords":["retrieval","generation"]}\n',
        encoding="utf-8",
    )

    questions = load_questions(questions_file)

    assert len(questions) == 1
    assert questions[0].id == "q1"
    assert questions[0].question == "What is RAG?"
    assert questions[0].expected_keywords == ["retrieval", "generation"]


@patch("scripts.eval.run_rag")
def test_evaluate_questions_computes_metrics(mock_run_rag) -> None:
    mock_run_rag.side_effect = [
        {"answer": "This uses retrieval and generation", "confidence": 0.8},
        {"answer": "This answer mentions retrieval", "confidence": 0.6},
    ]
    questions = [
        EvalQuestion(
            id="q1",
            question="Explain RAG",
            expected_keywords=["retrieval", "generation"],
        ),
        EvalQuestion(
            id="q2",
            question="What does retrieval do?",
            expected_keywords=["retrieval", "ranking"],
        ),
    ]

    summary = evaluate_questions(questions)

    assert summary["keyword_hit_rate"] == 0.75
    assert summary["avg_confidence"] == 0.7
    assert summary["total_samples"] == 2
    assert summary["successful_samples"] == 2
    assert summary["failed_samples"] == 0


@patch("scripts.eval.run_rag")
def test_evaluate_questions_tolerates_runtime_errors(mock_run_rag) -> None:
    mock_run_rag.side_effect = [
        RuntimeError("temporary failure"),
        {"answer": "retrieval and generation", "confidence": 0.9},
    ]
    questions = [
        EvalQuestion(
            id="q1",
            question="Question 1",
            expected_keywords=["retrieval", "generation"],
        ),
        EvalQuestion(
            id="q2",
            question="Question 2",
            expected_keywords=["retrieval", "generation"],
        ),
    ]

    summary = evaluate_questions(questions)

    assert summary["keyword_hit_rate"] == 0.5
    assert summary["avg_confidence"] == 0.9
    assert summary["total_samples"] == 2
    assert summary["successful_samples"] == 1
    assert summary["failed_samples"] == 1
