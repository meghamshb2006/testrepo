from __future__ import annotations

from unittest.mock import MagicMock

from evaluation.evaluators.retrieval_evaluator import RetrievalEvaluator
from evaluation.schemas import BenchmarkCase


def test_correct_source_at_rank_1() -> None:
    retrieval_service = MagicMock()
    retrieval_service.retrieve.return_value = {
        "candidate_count": 2,
        "result_count": 2,
        "results": [
            {
                "drawing_id": "drawing-001",
                "drawing_number": "DR-1001",
                "filename": "a.pdf",
            },
            {
                "drawing_id": "drawing-002",
                "drawing_number": "DR-2002",
                "filename": "b.pdf",
            },
        ],
        "context": "ctx",
    }

    evaluator = RetrievalEvaluator(retrieval_service)
    result = evaluator.evaluate_case(
        BenchmarkCase(
            case_id="case-1",
            question="Find DR-1001",
            expected_drawing_ids=["drawing-001"],
        )
    )

    assert result.hit_at_1 is True
    assert result.reciprocal_rank == 1.0
    assert result.latency_ms >= 0.0
    assert result.error is None


def test_correct_source_at_rank_3() -> None:
    retrieval_service = MagicMock()
    retrieval_service.retrieve.return_value = {
        "candidate_count": 3,
        "result_count": 3,
        "results": [
            {"drawing_id": "drawing-002", "drawing_number": "A", "filename": "a.pdf"},
            {"drawing_id": "drawing-003", "drawing_number": "B", "filename": "b.pdf"},
            {"drawing_id": "drawing-001", "drawing_number": "C", "filename": "c.pdf"},
        ],
        "context": "ctx",
    }

    evaluator = RetrievalEvaluator(retrieval_service)
    result = evaluator.evaluate_case(
        BenchmarkCase(
            case_id="case-2",
            question="Find drawing-001",
            expected_drawing_ids=["drawing-001"],
        )
    )

    assert result.hit_at_1 is False
    assert result.hit_at_3 is True
    assert result.reciprocal_rank == 1.0 / 3.0


def test_missing_expected_source() -> None:
    retrieval_service = MagicMock()
    retrieval_service.retrieve.return_value = {
        "candidate_count": 1,
        "result_count": 1,
        "results": [
            {
                "drawing_id": "drawing-999",
                "drawing_number": "ZZ",
                "filename": "z.pdf",
            }
        ],
        "context": "ctx",
    }

    evaluator = RetrievalEvaluator(retrieval_service)
    result = evaluator.evaluate_case(
        BenchmarkCase(
            case_id="case-3",
            question="Find drawing-001",
            expected_drawing_ids=["drawing-001"],
        )
    )

    assert result.hit_at_5 is False
    assert result.reciprocal_rank == 0.0


def test_errors_captured_without_aborting() -> None:
    retrieval_service = MagicMock()
    retrieval_service.retrieve.side_effect = RuntimeError("boom")

    evaluator = RetrievalEvaluator(retrieval_service)
    result = evaluator.evaluate_case(
        BenchmarkCase(
            case_id="case-4",
            question="Find drawing-001",
            expected_drawing_ids=["drawing-001"],
        )
    )

    assert result.error == "boom"
    assert result.hit_at_1 is False
    assert result.latency_ms >= 0.0
