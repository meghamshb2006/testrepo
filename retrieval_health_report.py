"""CLI for generating a retrieval health report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.config import SEARCH_DATABASE_PATH
from search.database import SearchDatabase
from search.diagnostics.health_report import RetrievalHealthReport
from search.repositories.search_repository import SearchRepository
from search.services.reindex_service import ReindexService
from search.services.retrieval_service import RetrievalService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a developer-facing retrieval health report."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="Path to drawing_search.db",
    )
    parser.add_argument(
        "--probe-query",
        type=str,
        default=None,
        help="Optional probe query for latency sampling.",
    )
    parser.add_argument(
        "--benchmark-json",
        type=Path,
        default=None,
        help="Optional evaluation JSON to embed summary metrics.",
    )
    parser.add_argument(
        "--output-markdown",
        type=Path,
        default=None,
        help="Write Markdown report to this path.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Write JSON report to this path.",
    )

    args = parser.parse_args()
    db_path = args.database or Path(SEARCH_DATABASE_PATH)
    database = SearchDatabase(str(db_path))

    try:
        database.initialize()
        repository = SearchRepository(database)
        reindex_service = ReindexService(database)
        retrieval_service = RetrievalService(repository=repository)
        builder = RetrievalHealthReport(
            reindex_service=reindex_service,
            retrieval_service=retrieval_service,
        )
        report = builder.build(
            probe_query=args.probe_query,
            benchmark_json=args.benchmark_json,
        )
        markdown = RetrievalHealthReport.to_markdown(report)

        if args.output_markdown is not None:
            args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
            args.output_markdown.write_text(markdown, encoding="utf-8")

        if args.output_json is not None:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(
                json.dumps(report, indent=2, default=str),
                encoding="utf-8",
            )

        if args.output_markdown is None and args.output_json is None:
            print(markdown)

        return 0 if report.get("ok") else 1

    except Exception as exc:
        print(f"Health report failed: {exc}", file=sys.stderr)
        return 1

    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
