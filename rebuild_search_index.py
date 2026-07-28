"""CLI for rebuilding and validating the lexical search index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.config import SEARCH_DATABASE_PATH
from search.database import SearchDatabase
from search.services.reindex_service import ReindexService


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild or validate the SQLite FTS lexical search index."
        )
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="Path to drawing_search.db",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate index integrity without rebuilding.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON.",
    )

    args = parser.parse_args()
    db_path = args.database or Path(SEARCH_DATABASE_PATH)
    database = SearchDatabase(str(db_path))

    try:
        service = ReindexService(database)

        if args.validate_only:
            payload = {"validation": service.validate_index()}
        else:
            payload = service.rebuild_index(force_fts=True)

        if args.json:
            print(json.dumps(payload, indent=2, default=str))
        else:
            validation = payload.get("validation") or {}
            rebuild = payload.get("rebuild")
            if rebuild is not None:
                print(
                    "FTS rebuilt="
                    f"{rebuild.get('rebuilt')} "
                    f"documents={rebuild.get('document_count')} "
                    f"fts={rebuild.get('fts_count')}"
                )
            integrity = validation.get("fts_integrity") or {}
            print(
                "Validation ok="
                f"{validation.get('ok')} "
                f"documents={validation.get('document_count')} "
                f"fts={integrity.get('fts_count')}"
            )

        if not (payload.get("validation") or {}).get("ok", False):
            return 1

        return 0

    except Exception as exc:
        print(f"Reindex failed: {exc}", file=sys.stderr)
        return 1

    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
