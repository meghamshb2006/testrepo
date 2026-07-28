"""Dataset / index management CLI for validation workflows."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import SEARCH_DATABASE_PATH
from evaluation.dataset_loader import BenchmarkDatasetLoader
from evaluation.schemas import BenchmarkCase, BenchmarkDataset
from search.database import SearchDatabase
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository
from search.services.bulk_ingestion_service import BulkIngestionService
from search.services.reindex_service import ReindexService


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, default=str))


def cmd_list(args: argparse.Namespace) -> int:
    database = SearchDatabase(str(args.database or Path(SEARCH_DATABASE_PATH)))
    try:
        database.initialize()
        repository = SearchRepository(database)
        documents = repository.list_all()

        if args.limit is not None:
            documents = documents[: args.limit]

        rows = [
            {
                "drawing_id": doc.get("drawing_id"),
                "filename": doc.get("filename"),
                "drawing_number": doc.get("drawing_number"),
                "revision": doc.get("revision"),
                "material": doc.get("material"),
                "updated_at": doc.get("updated_at"),
            }
            for doc in documents
        ]

        if args.json:
            _print_json({"count": len(rows), "documents": rows})
        else:
            print(f"Indexed drawings: {repository.count()}")
            for row in rows:
                print(
                    f"- {row['drawing_id']} | {row['filename']} | "
                    f"{row['drawing_number'] or '-'} | "
                    f"rev={row['revision'] or '-'} | "
                    f"{row['material'] or '-'}"
                )
        return 0
    finally:
        database.close()


def cmd_count(args: argparse.Namespace) -> int:
    database = SearchDatabase(str(args.database or Path(SEARCH_DATABASE_PATH)))
    try:
        database.initialize()
        repository = SearchRepository(database)
        reindex = ReindexService(database)
        validation = reindex.validate_index()
        payload = {
            "document_count": repository.count(),
            "fts_integrity": validation.get("fts_integrity"),
            "identifier_coverage": validation.get("identifier_coverage"),
        }
        if args.json:
            _print_json(payload)
        else:
            print(f"document_count={payload['document_count']}")
            integrity = payload["fts_integrity"] or {}
            print(
                f"fts_count={integrity.get('fts_count')} "
                f"ok={integrity.get('ok')}"
            )
        return 0 if (payload["fts_integrity"] or {}).get("ok") else 1
    finally:
        database.close()


def cmd_show(args: argparse.Namespace) -> int:
    database = SearchDatabase(str(args.database or Path(SEARCH_DATABASE_PATH)))
    try:
        database.initialize()
        repository = SearchRepository(database)
        document = repository.get_by_drawing_id(args.drawing_id)
        if document is None:
            print(f"Drawing not found: {args.drawing_id}", file=sys.stderr)
            return 1
        _print_json(dict(document))
        return 0
    finally:
        database.close()


def cmd_validate(args: argparse.Namespace) -> int:
    database = SearchDatabase(str(args.database or Path(SEARCH_DATABASE_PATH)))
    try:
        database.initialize()
        validation = ReindexService(database).validate_index()
        if args.json:
            _print_json(validation)
        else:
            integrity = validation.get("fts_integrity") or {}
            print(
                f"ok={validation.get('ok')} "
                f"documents={validation.get('document_count')} "
                f"fts={integrity.get('fts_count')}"
            )
            coverage = validation.get("identifier_coverage") or {}
            for key, value in coverage.items():
                print(f"coverage.{key}={float(value) * 100.0:.1f}%")
        return 0 if validation.get("ok") else 1
    finally:
        database.close()


def cmd_export_manifest(args: argparse.Namespace) -> int:
    database = SearchDatabase(str(args.database or Path(SEARCH_DATABASE_PATH)))
    try:
        database.initialize()
        repository = SearchRepository(database)
        documents = repository.list_all()
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database": str(args.database or Path(SEARCH_DATABASE_PATH)),
            "document_count": len(documents),
            "documents": [
                {
                    "drawing_id": doc.get("drawing_id"),
                    "filename": doc.get("filename"),
                    "drawing_number": doc.get("drawing_number"),
                    "revision": doc.get("revision"),
                    "title": doc.get("title"),
                    "material": doc.get("material"),
                    "part_numbers": doc.get("part_numbers"),
                }
                for doc in documents
            ],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(manifest, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"Wrote manifest: {args.output}")
        return 0
    finally:
        database.close()


def cmd_validate_benchmark(args: argparse.Namespace) -> int:
    dataset = BenchmarkDatasetLoader.load(args.dataset)
    database = SearchDatabase(str(args.database or Path(SEARCH_DATABASE_PATH)))
    try:
        database.initialize()
        repository = SearchRepository(database)
        indexed_ids = {
            str(doc.get("drawing_id")).casefold()
            for doc in repository.list_all()
            if doc.get("drawing_id")
        }
        indexed_numbers = {
            str(doc.get("drawing_number")).casefold()
            for doc in repository.list_all()
            if doc.get("drawing_number")
        }

        missing: list[dict[str, Any]] = []
        for case in dataset.cases:
            for drawing_id in case.expected_drawing_ids:
                if drawing_id.casefold() not in indexed_ids:
                    missing.append(
                        {
                            "case_id": case.case_id,
                            "expected_drawing_id": drawing_id,
                            "reason": "drawing_id_not_in_index",
                        }
                    )
            for number in case.expected_drawing_numbers:
                if number.casefold() not in indexed_numbers:
                    missing.append(
                        {
                            "case_id": case.case_id,
                            "expected_drawing_number": number,
                            "reason": "drawing_number_not_in_index",
                        }
                    )

        payload = {
            "dataset": dataset.name,
            "case_count": len(dataset.cases),
            "indexed_documents": len(indexed_ids),
            "missing_expectations": missing,
            "ok": len(missing) == 0,
        }
        if args.json:
            _print_json(payload)
        else:
            print(
                f"dataset={dataset.name} cases={payload['case_count']} "
                f"missing={len(missing)} ok={payload['ok']}"
            )
            for item in missing[:20]:
                print(f"- {item}")
        return 0 if payload["ok"] else 1
    finally:
        database.close()


def cmd_scaffold_benchmark(args: argparse.Namespace) -> int:
    database = SearchDatabase(str(args.database or Path(SEARCH_DATABASE_PATH)))
    try:
        database.initialize()
        repository = SearchRepository(database)
        documents = repository.list_all()[: args.limit]
        cases: list[BenchmarkCase] = []

        for document in documents:
            drawing_id = document.get("drawing_id")
            drawing_number = document.get("drawing_number")
            if not drawing_id:
                continue

            question_target = drawing_number or drawing_id
            cases.append(
                BenchmarkCase(
                    case_id=f"lookup-{drawing_id}",
                    question=f"Find drawing {question_target}",
                    expected_drawing_ids=[str(drawing_id)],
                    expected_drawing_numbers=(
                        [str(drawing_number)] if drawing_number else []
                    ),
                    expected_filenames=(
                        [str(document.get("filename"))]
                        if document.get("filename")
                        else []
                    ),
                    category="exact_lookup",
                    notes="Auto-scaffolded from index manifest.",
                )
            )

        dataset = BenchmarkDataset(
            name=args.name,
            version=args.version,
            description=(
                "Auto-scaffolded benchmark from the current search index. "
                "Review and enrich expected_answer_terms before using as golden."
            ),
            cases=cases,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            dataset.model_dump_json(indent=2),
            encoding="utf-8",
        )
        print(f"Wrote scaffold benchmark ({len(cases)} cases): {args.output}")
        return 0
    finally:
        database.close()


def cmd_seed_documents(args: argparse.Namespace) -> int:
    """Seed the index from a JSON array of SearchDocument payloads (offline)."""
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "documents" in payload:
        documents_raw = payload["documents"]
    elif isinstance(payload, list):
        documents_raw = payload
    else:
        raise ValueError(
            "Seed file must be a list of documents or an object with "
            "'documents'."
        )

    documents = [SearchDocument.model_validate(item) for item in documents_raw]
    database = SearchDatabase(str(args.database or Path(SEARCH_DATABASE_PATH)))
    try:
        database.initialize()
        repository = SearchRepository(database)
        report = BulkIngestionService(repository=repository).ingest_documents(
            documents,
            skip_existing=args.skip_existing,
        )
        payload_out = report.to_dict()
        if args.json:
            _print_json(payload_out)
        else:
            print(
                "Seeded documents: "
                f"succeeded={payload_out['succeeded']} "
                f"failed={payload_out['failed']} "
                f"skipped={payload_out['skipped']}"
            )
        return 1 if payload_out["failed"] else 0
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Manage indexed drawing datasets and benchmark readiness. "
            "Global options such as --database may appear before or after "
            "the subcommand when using the forms shown in --help."
        ),
    )
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--database",
        type=Path,
        default=None,
        help="Path to drawing_search.db (default: SEARCH_DATABASE_PATH).",
    )

    # Allow: manage_dataset.py --database X <cmd>
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser(
        "list",
        parents=[shared],
        help="List indexed drawings.",
    )
    list_parser.add_argument("--limit", type=int, default=None)
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=cmd_list)

    count_parser = subparsers.add_parser(
        "count",
        parents=[shared],
        help="Count indexed drawings.",
    )
    count_parser.add_argument("--json", action="store_true")
    count_parser.set_defaults(func=cmd_count)

    show_parser = subparsers.add_parser(
        "show",
        parents=[shared],
        help="Show one drawing row as JSON.",
    )
    show_parser.add_argument("drawing_id")
    show_parser.set_defaults(func=cmd_show)

    validate_parser = subparsers.add_parser(
        "validate-index",
        parents=[shared],
        help="Validate FTS integrity and field coverage.",
    )
    validate_parser.add_argument("--json", action="store_true")
    validate_parser.set_defaults(func=cmd_validate)

    export_parser = subparsers.add_parser(
        "export-manifest",
        parents=[shared],
        help="Export a lightweight index manifest JSON.",
    )
    export_parser.add_argument("--output", type=Path, required=True)
    export_parser.set_defaults(func=cmd_export_manifest)

    validate_bench = subparsers.add_parser(
        "validate-benchmark",
        parents=[shared],
        help="Check that benchmark expected IDs exist in the index.",
    )
    validate_bench.add_argument("--dataset", type=Path, required=True)
    validate_bench.add_argument("--json", action="store_true")
    validate_bench.set_defaults(func=cmd_validate_benchmark)

    scaffold = subparsers.add_parser(
        "scaffold-benchmark",
        parents=[shared],
        help="Generate a starter benchmark JSON from indexed drawings.",
    )
    scaffold.add_argument("--output", type=Path, required=True)
    scaffold.add_argument("--name", default="scaffolded-benchmark")
    scaffold.add_argument("--version", default="0.1.0")
    scaffold.add_argument("--limit", type=int, default=50)
    scaffold.set_defaults(func=cmd_scaffold_benchmark)

    seed = subparsers.add_parser(
        "seed-documents",
        parents=[shared],
        help="Upsert SearchDocuments from a JSON pack (no LLM required).",
    )
    seed.add_argument("--input", type=Path, required=True)
    seed.add_argument("--skip-existing", action="store_true")
    seed.add_argument("--json", action="store_true")
    seed.set_defaults(func=cmd_seed_documents)

    args = parser.parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"Dataset management failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
