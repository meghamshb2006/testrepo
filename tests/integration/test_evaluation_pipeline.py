from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from evaluation.evaluators.answer_evaluator import AnswerEvaluator
from evaluation.evaluators.retrieval_evaluator import RetrievalEvaluator
from evaluation.schemas import BenchmarkCase, BenchmarkDataset
from evaluation.services.evaluation_runner import EvaluationRunner
from search.database import SearchDatabase
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository
from search.services.question_answering_service import (
    DrawingQuestionAnsweringService,
)
from search.services.retrieval_service import RetrievalService
from tests.evaluation.conftest import FakeAnswerGenerator


def _seed_repository(tmp_path: Path) -> SearchRepository:
    database = SearchDatabase(str(tmp_path / "evaluation_pipeline.db"))
    database.initialize()
    repository = SearchRepository(database)
    now = datetime.now(timezone.utc)

    documents = [
        SearchDocument(
            drawing_id="drawing-001",
            filename="aluminium_mounting_bracket.pdf",
            drawing_number="DR-1001",
            revision="C",
            title="Aluminium Mounting Bracket",
            material="Aluminium 6061-T6",
            finish="Anodised",
            units="mm",
            part_numbers="BR-1001",
            dimensions_text="Length 120 mm Hole diameter 10.5 mm",
            tolerances_text="ISO-2768-mK plusminus 0.05 mm",
            notes_text="Surface finish anodized",
            searchable_text=(
                "DR-1001 aluminium mounting bracket 6061-T6 BR-1001 "
                "120 mm 10.5 mm ISO-2768-mK anodised"
            ),
            created_at=now,
            updated_at=now,
        ),
        SearchDocument(
            drawing_id="drawing-002",
            filename="stainless_motor_housing.pdf",
            drawing_number="DR-2002",
            title="Stainless Steel Motor Housing",
            material="Stainless Steel 316",
            searchable_text=(
                "DR-2002 stainless steel motor housing machine surfaces"
            ),
            created_at=now,
            updated_at=now,
        ),
        SearchDocument(
            drawing_id="drawing-003",
            filename="copper_busbar.pdf",
            drawing_number="DR-3003",
            title="Electrical Copper Busbar",
            material="Copper C110",
            searchable_text="DR-3003 copper busbar tin plated electrical",
            created_at=now,
            updated_at=now,
        ),
    ]

    for document in documents:
        repository.upsert(document)

    return repository


def test_evaluation_pipeline_with_real_retrieval_and_fake_answers(
    tmp_path: Path,
) -> None:
    repository = _seed_repository(tmp_path)
    retrieval_service = RetrievalService(repository=repository)
    fake_generator = FakeAnswerGenerator()
    qa_service = DrawingQuestionAnsweringService(
        retrieval_service=retrieval_service,
        answer_generator=fake_generator,
    )

    dataset = BenchmarkDataset(
        name="integration-mini",
        version="1.0",
        cases=[
            BenchmarkCase(
                case_id="exact-drawing-number",
                question="Find drawing DR-1001",
                expected_drawing_ids=["drawing-001"],
                expected_drawing_numbers=["DR-1001"],
                expected_answer_terms=["DR-1001"],
                answerable=True,
            ),
            BenchmarkCase(
                case_id="material-6061",
                question="What material is specified for BR-1001?",
                expected_drawing_ids=["drawing-001"],
                expected_answer_terms=["6061-T6"],
                answerable=True,
            ),
            BenchmarkCase(
                case_id="no-match-zz9999",
                question="What is the titanium alloy for part ZZ-9999?",
                answerable=False,
            ),
        ],
    )

    runner = EvaluationRunner(
        retrieval_evaluator=RetrievalEvaluator(retrieval_service),
        answer_evaluator=AnswerEvaluator(qa_service),
    )
    evaluation = runner.run(dataset, evaluate_answers=True)
    summary = evaluation["summary"]

    assert summary["hit_at_1"] > 0.0
    assert summary["refusal_accuracy"] == 1.0
    assert summary["answer_cases"] == 3
    assert summary["failures"] == 0
    assert fake_generator.calls

    repository.database.close()


def test_sample_benchmark_json_loads() -> None:
    project_root = Path(__file__).resolve().parents[2]
    dataset_path = (
        project_root / "evaluation" / "datasets" / "sample_benchmark.json"
    )
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))

    assert payload["name"]
    assert len(payload["cases"]) >= 8
