"""Automated regression benchmarking against a stored baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.config import SEARCH_DATABASE_PATH
from evaluation.dataset_loader import BenchmarkDatasetLoader
from evaluation.evaluators.retrieval_evaluator import RetrievalEvaluator
from evaluation.reporting.report_builder import EvaluationReportBuilder
from evaluation.services.evaluation_runner import EvaluationRunner
from search.database import SearchDatabase
from search.repositories.search_repository import SearchRepository
from search.services.retrieval_service import RetrievalService


_DEFAULT_METRICS = (
    "hit_at_1",
    "hit_at_3",
    "hit_at_5",
    "mean_reciprocal_rank",
)


def compare_to_baseline(
    current_summary: dict[str, Any],
    baseline_summary: dict[str, Any],
    *,
    metrics: tuple[str, ...] = _DEFAULT_METRICS,
    max_regression: float = 0.05,
) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    regressions = 0

    for metric in metrics:
        current = float(current_summary.get(metric) or 0.0)
        baseline = float(baseline_summary.get(metric) or 0.0)
        delta = current - baseline
        regressed = delta < -abs(max_regression)
        if regressed:
            regressions += 1
        comparisons.append(
            {
                "metric": metric,
                "baseline": baseline,
                "current": current,
                "delta": round(delta, 6),
                "regressed": regressed,
            }
        )

    return {
        "comparisons": comparisons,
        "regression_count": regressions,
        "ok": regressions == 0,
        "max_regression": max_regression,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run retrieval regression benchmarks and optionally compare "
            "against a baseline evaluation JSON."
        )
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--database", type=Path, default=None)
    parser.add_argument("--candidate-limit", type=int, default=30)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-context-characters", type=int, default=16000)
    parser.add_argument("--baseline-json", type=Path, default=None)
    parser.add_argument(
        "--max-regression",
        type=float,
        default=0.05,
        help="Allowed absolute drop vs baseline before failing (default 0.05).",
    )
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-markdown", type=Path, default=None)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument(
        "--update-baseline",
        type=Path,
        default=None,
        help="Write the current evaluation JSON as a new baseline file.",
    )
    parser.add_argument("--quiet", action="store_true")

    args = parser.parse_args()
    db_path = args.database or Path(SEARCH_DATABASE_PATH)
    database = SearchDatabase(str(db_path))

    try:
        dataset = BenchmarkDatasetLoader.load(args.dataset)
        database.initialize()
        repository = SearchRepository(database)
        runner = EvaluationRunner(
            retrieval_evaluator=RetrievalEvaluator(
                RetrievalService(repository=repository)
            )
        )
        evaluation = runner.run(
            dataset=dataset,
            evaluate_answers=False,
            default_candidate_limit=args.candidate_limit,
            default_top_k=args.top_k,
            default_max_context_characters=args.max_context_characters,
        )

        comparison = None
        if args.baseline_json is not None:
            baseline = json.loads(
                args.baseline_json.read_text(encoding="utf-8")
            )
            baseline_summary = baseline.get("summary") or {}
            comparison = compare_to_baseline(
                evaluation["summary"],
                baseline_summary,
                max_regression=args.max_regression,
            )
            evaluation["regression"] = comparison

        if args.output_json is not None:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(
                EvaluationReportBuilder.to_json(evaluation),
                encoding="utf-8",
            )

        if args.output_markdown is not None:
            args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
            args.output_markdown.write_text(
                EvaluationReportBuilder.to_markdown(evaluation),
                encoding="utf-8",
            )

        if args.output_csv is not None:
            args.output_csv.parent.mkdir(parents=True, exist_ok=True)
            args.output_csv.write_text(
                EvaluationReportBuilder.to_csv(evaluation),
                encoding="utf-8",
            )

        if args.update_baseline is not None:
            args.update_baseline.parent.mkdir(parents=True, exist_ok=True)
            args.update_baseline.write_text(
                EvaluationReportBuilder.to_json(evaluation),
                encoding="utf-8",
            )

        summary = evaluation["summary"]
        if not args.quiet:
            print(f"Dataset: {evaluation['dataset']['name']}")
            print(f"Hit@1: {summary['hit_at_1'] * 100:.1f}%")
            print(f"Hit@5: {summary['hit_at_5'] * 100:.1f}%")
            print(f"MRR: {summary['mean_reciprocal_rank']:.2f}")
            if comparison is not None:
                print(
                    "Regression check: "
                    f"ok={comparison['ok']} "
                    f"regressions={comparison['regression_count']}"
                )
                for item in comparison["comparisons"]:
                    print(
                        f"  {item['metric']}: "
                        f"{item['baseline']:.3f} -> {item['current']:.3f} "
                        f"(delta={item['delta']:+.3f})"
                    )

        if comparison is not None and not comparison["ok"]:
            return 1

        if summary.get("failures", 0) > 0:
            return 1

        return 0

    except Exception as exc:
        print(f"Regression benchmark failed: {exc}", file=sys.stderr)
        return 1

    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
