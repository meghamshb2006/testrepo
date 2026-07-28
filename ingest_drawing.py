"""CLI entry point for ingesting engineering drawing PDFs into the search index."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from search.database import SearchDatabase
from search.repositories.search_repository import SearchRepository
from search.services.drawing_ingestion_service import DrawingIngestionService


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest a single engineering drawing PDF into the lexical "
            "search index (drawing_search.db)."
        )
    )
    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Path to the PDF file to ingest.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help=(
            "Override search database path "
            "(default: SEARCH_DATABASE_PATH / data/drawing_search.db)."
        ),
    )

    args = parser.parse_args()

    db_path = str(args.db_path) if args.db_path else None
    database = SearchDatabase(db_path=db_path)

    try:
        database.initialize()
        repository = SearchRepository(database)
        service = DrawingIngestionService(repository=repository)

        result = service.ingest_pdf(args.pdf_path)

        print(f"Ingested: {result['filename']}")
        print(f"Drawing ID: {result['drawing_id']}")
        print(f"Pages: {result['page_count']}")

        return 0

    except Exception as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1

    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
