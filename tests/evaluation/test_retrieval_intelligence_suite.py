from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from evaluation.dataset_loader import BenchmarkDatasetLoader
from evaluation.evaluators.retrieval_evaluator import RetrievalEvaluator
from evaluation.services.evaluation_runner import EvaluationRunner
from search.database import SearchDatabase
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository
from search.services.retrieval_service import RetrievalService


def test_retrieval_intelligence_suite_runs_on_seeded_db(
    tmp_path: Path,
) -> None:
    database = SearchDatabase(str(tmp_path / "m71.db"))
    database.initialize()
    repository = SearchRepository(database)
    now = datetime.now(timezone.utc)

    repository.upsert(
        SearchDocument(
            drawing_id="drawing-001",
            filename="mounting_bracket.pdf",
            drawing_number="DR-1023",
            revision="C",
            title="Mounting Bracket",
            material="Aluminium 6061-T6",
            part_numbers="BR-1001",
            tolerances_text="ISO-2768-mK",
            engineering_standards="ISO-2768-MK",
            components="BR-1001 mounting hole",
            body="Bracket for motor assembly",
            searchable_text=(
                "DR-1023 mounting bracket aluminium 6061-T6 BR-1001 "
                "ISO-2768-mK revision C"
            ),
            created_at=now,
            updated_at=now,
        )
    )

    suite_path = (
        Path(__file__).resolve().parents[2]
        / "evaluation"
        / "datasets"
        / "retrieval_intelligence_suites.json"
    )
    dataset = BenchmarkDatasetLoader.load(suite_path)
    runner = EvaluationRunner(
        retrieval_evaluator=RetrievalEvaluator(
            RetrievalService(repository=repository)
        )
    )
    evaluation = runner.run(dataset)

    summary = evaluation["summary"]
    assert summary["total_cases"] == 7
    assert summary["mean_context_length"] >= 0.0
    assert "confidence_high_rate" in summary
    assert summary["confidence_accuracy"] is not None
    assert summary["failures"] == 0

    database.close()
