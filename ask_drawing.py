"""CLI for grounded engineering drawing question answering."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.config import SEARCH_DATABASE_PATH
from search.database import SearchDatabase
from search.repositories.search_repository import SearchRepository
from search.services.question_answering_service import (
    DrawingQuestionAnsweringService,
)
from search.services.retrieval_service import RetrievalService


def _format_source_line(index: int, source: dict) -> str:
    drawing_number = source.get("drawing_number") or "unknown"
    revision = source.get("revision")
    filename = source.get("filename") or "unknown"

    if revision:
        return f"{index}. {drawing_number} Rev {revision} - {filename}"

    return f"{index}. {drawing_number} - {filename}"


def _print_human_readable(response: dict, show_context: bool) -> None:
    print("Answer:")
    print(response["answer"])
    print()
    print("Sources:")

    sources = response.get("sources", [])

    if not sources:
        print("None")
    else:
        for index, source in enumerate(sources, start=1):
            print(_format_source_line(index, source))

    if show_context:
        print()
        print("Context:")
        print(response.get("context") or "(empty)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Ask a grounded question over indexed engineering drawings."
        )
    )
    parser.add_argument(
        "question",
        type=str,
        help="Question to answer using indexed drawing data.",
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
        help="Maximum FTS5 candidates to retrieve.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Maximum BM25-ranked results to use.",
    )
    parser.add_argument(
        "--max-context-characters",
        type=int,
        default=16000,
        help="Maximum retrieved context length.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print the full structured response as JSON.",
    )
    parser.add_argument(
        "--show-context",
        action="store_true",
        help="Print retrieved context after the answer.",
    )

    args = parser.parse_args()

    db_path = args.database or Path(SEARCH_DATABASE_PATH)
    database = SearchDatabase(str(db_path))

    try:
        database.initialize()
        repository = SearchRepository(database)
        retrieval_service = RetrievalService(repository=repository)
        qa_service = DrawingQuestionAnsweringService(
            retrieval_service=retrieval_service,
        )

        response = qa_service.answer(
            question=args.question,
            candidate_limit=args.candidate_limit,
            top_k=args.top_k,
            max_context_characters=args.max_context_characters,
        )

        if args.json_output:
            print(json.dumps(response, indent=2, default=str))
        else:
            _print_human_readable(response, show_context=args.show_context)

        return 0

    except RuntimeError as exc:
        print(f"Question answering failed: {exc}", file=sys.stderr)
        return 1

    except ValueError as exc:
        print(f"Invalid input: {exc}", file=sys.stderr)
        return 1

    except Exception as exc:
        print(f"Question answering failed: {exc}", file=sys.stderr)
        return 1

    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
