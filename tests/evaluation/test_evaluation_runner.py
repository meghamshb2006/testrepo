from __future__ import annotations

from unittest.mock import MagicMock

from evaluation.evaluators.answer_evaluator import AnswerEvaluator
from evaluation.evaluators.retrieval_evaluator import RetrievalEvaluator
from evaluation.schemas import BenchmarkCase, BenchmarkDataset
from evaluation.services.evaluation_runner import EvaluationRunner
from search.services.question_answering_service import NO_EVIDENCE_ANSWER


def _dataset() -> BenchmarkDataset:
    return BenchmarkDataset(
        name="demo",
        version="1.0",
        cases=[
            BenchmarkCase(
                case_id="case-a",
                question="Find DR-1001",
                expected_drawing_ids=["drawing-001"],
                expected_answer_terms=["DR-1001"],
                answerable=True,
                top_k=2,
                candidate_limit=5,
            ),
            BenchmarkCase(
                case_id="case-b",
                question="What about ZZ-9999?",
                answerable=False,
            ),
        ],
    )


def test_preserves_case_order_and_optional_answers() -> None:
    retrieval_service = MagicMock()
    retrieval_service.retrieve.side_effect = [
        {
            "candidate_count": 1,
            "result_count": 1,
            "results": [
                {
                    "drawing_id": "drawing-001",
                    "drawing_number": "DR-1001",
                    "filename": "a.pdf",
                }
            ],
            "context": "ctx",
        },
        {
            "candidate_count": 0,
            "result_count": 0,
            "results": [],
            "context": "",
        },
    ]

    qa_service = MagicMock()
    qa_service.answer.side_effect = [
        {
            "answer": "Drawing DR-1001",
            "grounded": True,
            "sources": [
                {
                    "drawing_id": "drawing-001",
                    "drawing_number": "DR-1001",
                    "filename": "a.pdf",
                }
            ],
        },
        {
            "answer": NO_EVIDENCE_ANSWER,
            "grounded": False,
            "sources": [],
        },
    ]

    runner = EvaluationRunner(
        retrieval_evaluator=RetrievalEvaluator(retrieval_service),
        answer_evaluator=AnswerEvaluator(qa_service),
    )

    evaluation = runner.run(_dataset(), evaluate_answers=True)
    summary = evaluation["summary"]

    assert [item["case_id"] for item in evaluation["retrieval_results"]] == [
        "case-a",
        "case-b",
    ]
    assert summary["hit_at_1"] == 0.5
    assert summary["answer_cases"] == 2
    assert summary["refusal_accuracy"] == 1.0
    assert summary["failures"] == 0


def test_continues_after_case_failure() -> None:
    retrieval_service = MagicMock()
    retrieval_service.retrieve.side_effect = [
        RuntimeError("first failed"),
        {
            "candidate_count": 1,
            "result_count": 1,
            "results": [
                {
                    "drawing_id": "drawing-001",
                    "drawing_number": "DR-1001",
                    "filename": "a.pdf",
                }
            ],
            "context": "ctx",
        },
    ]

    runner = EvaluationRunner(
        retrieval_evaluator=RetrievalEvaluator(retrieval_service),
    )
    # Second case expects no drawing; use a dataset where case-b has no expected IDs
    # and case-a fails, then a third call is not needed. Re-run with matching dataset.
    dataset = BenchmarkDataset(
        name="demo",
        version="1.0",
        cases=[
            BenchmarkCase(
                case_id="case-a",
                question="Find DR-1001",
                expected_drawing_ids=["drawing-001"],
            ),
            BenchmarkCase(
                case_id="case-b",
                question="Find DR-1001 again",
                expected_drawing_ids=["drawing-001"],
            ),
        ],
    )
    evaluation = runner.run(dataset, evaluate_answers=False)

    assert evaluation["summary"]["failures"] == 1
    assert evaluation["retrieval_results"][0]["error"] == "first failed"
    assert evaluation["retrieval_results"][1]["hit_at_1"] is True
    assert evaluation["retrieval_results"][1]["reciprocal_rank"] == 1.0

def test_case_specific_limits_override_defaults() -> None:
    retrieval_service = MagicMock()
    retrieval_service.retrieve.return_value = {
        "candidate_count": 1,
        "result_count": 1,
        "results": [
            {
                "drawing_id": "drawing-001",
                "drawing_number": "DR-1001",
                "filename": "a.pdf",
            }
        ],
        "context": "ctx",
    }

    runner = EvaluationRunner(
        retrieval_evaluator=RetrievalEvaluator(retrieval_service),
    )
    runner.run(
        BenchmarkDataset(
            name="demo",
            version="1.0",
            cases=[
                BenchmarkCase(
                    case_id="case-a",
                    question="Find DR-1001",
                    expected_drawing_ids=["drawing-001"],
                    candidate_limit=5,
                    top_k=2,
                    max_context_characters=1000,
                )
            ],
        ),
        default_candidate_limit=30,
        default_top_k=5,
        default_max_context_characters=16000,
    )

    retrieval_service.retrieve.assert_called_once_with(
        query="Find DR-1001",
        candidate_limit=5,
        top_k=2,
        max_context_characters=1000,
    )
