"""CLI for bulk ingestion of engineering drawing PDFs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.config import SEARCH_DATABASE_PATH
from search.database import SearchDatabase
from search.repositories.search_repository import SearchRepository
from search.services.bulk_ingestion_service import BulkIngestionService
from search.services.drawing_ingestion_service import DrawingIngestionService


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bulk-ingest engineering drawing PDFs from a directory "
            "into the lexical search index."
        )
    )
    parser.add_argument(
        "source_dir",
        type=Path,
        help="Directory containing PDF drawings.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="Path to drawing_search.db",
    )
    parser.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Recurse into subdirectories (default: true).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip PDFs whose content hash is already indexed.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop after the first failed PDF.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Ingest at most N PDFs.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Write an ingest report JSON.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file progress lines.",
    )

    args = parser.parse_args()
    db_path = args.database or Path(SEARCH_DATABASE_PATH)
    database = SearchDatabase(str(db_path))

    try:
        database.initialize()
        repository = SearchRepository(database)
        service = BulkIngestionService(
            repository=repository,
            ingestion_service=DrawingIngestionService(repository=repository),
        )

        def _progress(index: int, total: int, path: Path) -> None:
            if args.quiet:
                return
            print(f"[{index}/{total}] {path.name}")

        report = service.ingest_directory(
            args.source_dir,
            recursive=args.recursive,
            continue_on_error=not args.stop_on_error,
            skip_existing=args.skip_existing,
            limit=args.limit,
            progress_callback=_progress,
        )
        payload = report.to_dict()

        if args.output_json is not None:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(
                json.dumps(payload, indent=2, default=str),
                encoding="utf-8",
            )

        print(
            "Bulk ingest complete: "
            f"total={payload['total_files']} "
            f"succeeded={payload['succeeded']} "
            f"failed={payload['failed']} "
            f"skipped={payload['skipped']} "
            f"elapsed_ms={payload['elapsed_ms']}"
        )

        return 1 if payload["failed"] > 0 else 0

    except Exception as exc:
        print(f"Bulk ingest failed: {exc}", file=sys.stderr)
        return 1

    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
