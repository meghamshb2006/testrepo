from __future__ import annotations

import pytest
from pydantic import ValidationError

from evaluation.schemas import BenchmarkCase, BenchmarkDataset


def test_valid_benchmark_dataset_accepted() -> None:
    dataset = BenchmarkDataset(
        name="demo",
        version="1.0",
        cases=[
            BenchmarkCase(
                case_id="case-1",
                question="What material is used?",
                expected_drawing_ids=["drawing-001"],
            )
        ],
    )

    assert dataset.name == "demo"
    assert len(dataset.cases) == 1


def test_duplicate_case_id_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate case_id"):
        BenchmarkDataset(
            name="demo",
            version="1.0",
            cases=[
                BenchmarkCase(case_id="dup", question="Q1"),
                BenchmarkCase(case_id="dup", question="Q2"),
            ],
        )


def test_blank_question_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        BenchmarkCase(case_id="case-1", question="   ")


def test_invalid_limits_rejected() -> None:
    with pytest.raises(ValidationError, match="must be an integer >= 1"):
        BenchmarkCase(
            case_id="case-1",
            question="What material?",
            top_k=0,
        )


def test_top_k_greater_than_candidate_limit_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="top_k must not exceed candidate_limit",
    ):
        BenchmarkCase(
            case_id="case-1",
            question="What material?",
            candidate_limit=2,
            top_k=5,
        )
