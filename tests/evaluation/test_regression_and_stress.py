from __future__ import annotations

import json
from pathlib import Path

from run_regression_benchmark import compare_to_baseline
from search.database import SearchDatabase
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository
from search.services.bulk_ingestion_service import BulkIngestionService
from search.services.retrieval_service import RetrievalService
from stress_test_retrieval import run_stress
from evaluation.dataset_loader import BenchmarkDatasetLoader
from evaluation.evaluators.retrieval_evaluator import RetrievalEvaluator
from evaluation.reporting.report_builder import EvaluationReportBuilder
from evaluation.services.evaluation_runner import EvaluationRunner


def test_compare_to_baseline_detects_regression() -> None:
    comparison = compare_to_baseline(
        {"hit_at_1": 0.70, "hit_at_3": 0.90, "hit_at_5": 0.95, "mean_reciprocal_rank": 0.80},
        {"hit_at_1": 0.90, "hit_at_3": 0.90, "hit_at_5": 0.95, "mean_reciprocal_rank": 0.80},
        max_regression=0.05,
    )

    assert comparison["ok"] is False
    assert comparison["regression_count"] == 1


def test_golden_benchmark_and_stress(tmp_path: Path) -> None:
    seed_path = (
        Path(__file__).resolve().parents[2]
        / "evaluation"
        / "datasets"
        / "golden_seed_documents.json"
    )
    benchmark_path = (
        Path(__file__).resolve().parents[2]
        / "evaluation"
        / "datasets"
        / "golden_retrieval_benchmark.json"
    )
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    documents = [
        SearchDocument.model_validate(item)
        for item in payload["documents"]
    ]

    database = SearchDatabase(str(tmp_path / "golden_eval.db"))
    database.initialize()
    repository = SearchRepository(database)
    BulkIngestionService(repository=repository).ingest_documents(documents)

    dataset = BenchmarkDatasetLoader.load(benchmark_path)
    runner = EvaluationRunner(
        retrieval_evaluator=RetrievalEvaluator(
            RetrievalService(repository=repository)
        )
    )
    evaluation = runner.run(dataset)
    summary = evaluation["summary"]

    assert summary["failures"] == 0
    assert summary["hit_at_1"] >= 0.5
    assert "category_metrics" in summary
    assert summary["category_metrics"]

    markdown = EvaluationReportBuilder.to_markdown(evaluation)
    assert "Category Breakdown" in markdown

    stress = run_stress(
        RetrievalService(repository=repository),
        [case.question for case in dataset.cases[:3]],
        iterations=2,
        warmup=0,
    )
    assert stress["completed_requests"] == 6
    assert stress["error_count"] == 0
    assert stress["latency_p95_ms"] >= 0.0

    database.close()
