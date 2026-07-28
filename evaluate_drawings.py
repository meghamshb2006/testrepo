"""CLI for evaluating engineering drawing retrieval and answer quality."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import SEARCH_DATABASE_PATH
from evaluation.dataset_loader import BenchmarkDatasetLoader
from evaluation.evaluators.answer_evaluator import AnswerEvaluator
from evaluation.evaluators.retrieval_evaluator import RetrievalEvaluator
from evaluation.reporting.report_builder import EvaluationReportBuilder
from evaluation.services.evaluation_runner import EvaluationRunner
from search.database import SearchDatabase
from search.repositories.search_repository import SearchRepository
from search.services.question_answering_service import (
    DrawingQuestionAnsweringService,
)
from search.services.retrieval_service import RetrievalService


def _print_summary(evaluation: dict, quiet: bool) -> None:
    if quiet:
        return

    summary = evaluation["summary"]
    dataset = evaluation["dataset"]

    print(f"Dataset: {dataset['name']} v{dataset['version']}")
    print(f"Cases: {summary['total_cases']}")
    print(f"Hit@1: {summary['hit_at_1'] * 100.0:.1f}%")
    print(f"Hit@3: {summary['hit_at_3'] * 100.0:.1f}%")
    print(f"Hit@5: {summary['hit_at_5'] * 100.0:.1f}%")
    print(f"MRR: {summary['mean_reciprocal_rank']:.2f}")
    print(
        "Mean retrieval latency: "
        f"{summary['retrieval_latency_mean_ms']:.1f} ms"
    )
    print(f"Failures: {summary['failures']}")


def _thresholds_failed(args: argparse.Namespace, summary: dict) -> bool:
    if (
        args.fail_below_hit_at_1 is not None
        and summary["hit_at_1"] < args.fail_below_hit_at_1
    ):
        return True

    if (
        args.fail_below_hit_at_5 is not None
        and summary["hit_at_5"] < args.fail_below_hit_at_5
    ):
        return True

    if (
        args.fail_below_mrr is not None
        and summary["mean_reciprocal_rank"] < args.fail_below_mrr
    ):
        return True

    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate engineering drawing retrieval (and optionally "
            "grounded answers) against a JSON benchmark dataset. "
            "Retrieval-only mode does not require API credentials."
        )
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Path to a JSON benchmark dataset.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="Path to the search SQLite database.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=30,
        help="Default FTS5 candidate limit.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Default BM25 top-k.",
    )
    parser.add_argument(
        "--max-context-characters",
        type=int,
        default=16000,
        help="Default maximum context characters.",
    )
    parser.add_argument(
        "--evaluate-answers",
        action="store_true",
        help="Also evaluate grounded answers (may require API config).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Write the full evaluation report as JSON.",
    )
    parser.add_argument(
        "--output-markdown",
        type=Path,
        default=None,
        help="Write the evaluation report as Markdown.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Write per-case retrieval metrics as CSV.",
    )
    parser.add_argument(
        "--fail-below-hit-at-1",
        type=float,
        default=None,
        help="Fail if Hit@1 is below this ratio (0.0-1.0).",
    )
    parser.add_argument(
        "--fail-below-hit-at-5",
        type=float,
        default=None,
        help="Fail if Hit@5 is below this ratio (0.0-1.0).",
    )
    parser.add_argument(
        "--fail-below-mrr",
        type=float,
        default=None,
        help="Fail if MRR is below this value (0.0-1.0).",
    )
    parser.add_argument(
        "--fail-on-case-error",
        action="store_true",
        help="Return non-zero if any case reports an error.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the terminal summary.",
    )

    args = parser.parse_args()
    db_path = args.database or Path(SEARCH_DATABASE_PATH)
    database = SearchDatabase(str(db_path))

    try:
        dataset = BenchmarkDatasetLoader.load(args.dataset)
        database.initialize()

        repository = SearchRepository(database)
        retrieval_service = RetrievalService(repository=repository)
        retrieval_evaluator = RetrievalEvaluator(retrieval_service)

        answer_evaluator = None

        if args.evaluate_answers:
            qa_service = DrawingQuestionAnsweringService(
                retrieval_service=retrieval_service,
            )
            answer_evaluator = AnswerEvaluator(qa_service)

        runner = EvaluationRunner(
            retrieval_evaluator=retrieval_evaluator,
            answer_evaluator=answer_evaluator,
        )
        evaluation = runner.run(
            dataset=dataset,
            evaluate_answers=args.evaluate_answers,
            default_candidate_limit=args.candidate_limit,
            default_top_k=args.top_k,
            default_max_context_characters=args.max_context_characters,
        )

        _print_summary(evaluation, quiet=args.quiet)

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

        summary = evaluation["summary"]

        if args.fail_on_case_error and summary["failures"] > 0:
            print(
                f"Evaluation failed: {summary['failures']} case error(s).",
                file=sys.stderr,
            )
            return 1

        if _thresholds_failed(args, summary):
            print(
                "Evaluation failed: one or more metric thresholds were not met.",
                file=sys.stderr,
            )
            return 1

        return 0

    except ValueError as exc:
        print(f"Invalid input: {exc}", file=sys.stderr)
        return 1

    except Exception as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1

    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
