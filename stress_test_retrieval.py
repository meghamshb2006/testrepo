"""Stress-test utilities for lexical retrieval latency and throughput."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from app.config import SEARCH_DATABASE_PATH
from evaluation.dataset_loader import BenchmarkDatasetLoader
from evaluation.metrics import percentile
from search.database import SearchDatabase
from search.repositories.search_repository import SearchRepository
from search.services.retrieval_service import RetrievalService


def run_stress(
    retrieval_service: RetrievalService,
    queries: list[str],
    *,
    iterations: int = 1,
    candidate_limit: int = 30,
    top_k: int = 5,
    warmup: int = 0,
) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be >= 1.")

    if not queries:
        raise ValueError("queries must not be empty.")

    for _ in range(max(warmup, 0)):
        retrieval_service.retrieve(
            queries[0],
            candidate_limit=candidate_limit,
            top_k=top_k,
        )

    latencies_ms: list[float] = []
    errors: list[dict[str, str]] = []
    result_counts: list[int] = []

    wall_started = time.perf_counter()

    for _ in range(iterations):
        for query in queries:
            started = time.perf_counter()
            try:
                response = retrieval_service.retrieve(
                    query,
                    candidate_limit=candidate_limit,
                    top_k=top_k,
                )
                latencies_ms.append(
                    (time.perf_counter() - started) * 1000.0
                )
                result_counts.append(int(response.get("result_count") or 0))
            except Exception as exc:
                errors.append({"query": query, "error": str(exc)})

    wall_ms = (time.perf_counter() - wall_started) * 1000.0
    completed = len(latencies_ms)

    return {
        "query_count": len(queries),
        "iterations": iterations,
        "completed_requests": completed,
        "error_count": len(errors),
        "errors": errors,
        "wall_ms": round(wall_ms, 3),
        "throughput_qps": (
            round(completed / (wall_ms / 1000.0), 3) if wall_ms > 0 else 0.0
        ),
        "latency_mean_ms": round(
            statistics.fmean(latencies_ms) if latencies_ms else 0.0,
            3,
        ),
        "latency_p50_ms": round(percentile(latencies_ms, 50.0), 3),
        "latency_p95_ms": round(percentile(latencies_ms, 95.0), 3),
        "latency_p99_ms": round(percentile(latencies_ms, 99.0), 3),
        "latency_max_ms": round(max(latencies_ms) if latencies_ms else 0.0, 3),
        "mean_result_count": round(
            statistics.fmean(result_counts) if result_counts else 0.0,
            3,
        ),
    }


def _load_queries(args: argparse.Namespace) -> list[str]:
    if args.dataset is not None:
        dataset = BenchmarkDatasetLoader.load(args.dataset)
        return [case.question for case in dataset.cases]

    if args.queries_file is not None:
        lines = args.queries_file.read_text(encoding="utf-8").splitlines()
        return [line.strip() for line in lines if line.strip()]

    if args.query:
        return list(args.query)

    raise ValueError(
        "Provide --dataset, --queries-file, or one or more --query values."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Stress-test lexical retrieval latency (no ranking changes)."
        )
    )
    parser.add_argument("--database", type=Path, default=None)
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--queries-file", type=Path, default=None)
    parser.add_argument(
        "--query",
        action="append",
        default=None,
        help="Repeatable query string.",
    )
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--candidate-limit", type=int, default=30)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument(
        "--fail-above-p95-ms",
        type=float,
        default=None,
        help="Exit non-zero if p95 latency exceeds this threshold.",
    )

    args = parser.parse_args()
    db_path = args.database or Path(SEARCH_DATABASE_PATH)
    database = SearchDatabase(str(db_path))

    try:
        queries = _load_queries(args)
        database.initialize()
        repository = SearchRepository(database)
        service = RetrievalService(repository=repository)
        report = run_stress(
            service,
            queries,
            iterations=args.iterations,
            candidate_limit=args.candidate_limit,
            top_k=args.top_k,
            warmup=args.warmup,
        )

        if args.output_json is not None:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(
                json.dumps(report, indent=2),
                encoding="utf-8",
            )

        print(
            "Stress test: "
            f"requests={report['completed_requests']} "
            f"errors={report['error_count']} "
            f"mean={report['latency_mean_ms']}ms "
            f"p95={report['latency_p95_ms']}ms "
            f"qps={report['throughput_qps']}"
        )

        if report["error_count"] > 0:
            return 1

        if (
            args.fail_above_p95_ms is not None
            and report["latency_p95_ms"] > args.fail_above_p95_ms
        ):
            print(
                "p95 latency exceeded threshold "
                f"{args.fail_above_p95_ms} ms",
                file=sys.stderr,
            )
            return 1

        return 0

    except Exception as exc:
        print(f"Stress test failed: {exc}", file=sys.stderr)
        return 1

    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
