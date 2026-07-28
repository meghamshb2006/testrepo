"""Utilities for rebuilding and validating the lexical search index."""

from __future__ import annotations

from typing import Any

from search.database import SearchDatabase
from search.repositories.search_repository import SearchRepository


_RICH_FIELDS = (
    "engineering_standards",
    "components",
    "body",
    "sheet_number",
    "scale",
    "part_number",
    "manufacturing_process",
    "referenced_parts",
    "engineering_notes",
)

_IDENTITY_FIELDS = (
    "drawing_number",
    "revision",
    "material",
    "part_numbers",
)


class ReindexService:
    """Idempotent rebuild and validation helpers for drawing_search.db."""

    def __init__(self, database: SearchDatabase) -> None:
        self.database = database
        self.repository = SearchRepository(database)

    def rebuild_index(self, force_fts: bool = True) -> dict[str, Any]:
        self.database.initialize()
        rebuild = self.database.rebuild_fts(force=force_fts)
        validation = self.validate_index()
        return {
            "rebuild": rebuild,
            "validation": validation,
        }

    def validate_index(self) -> dict[str, Any]:
        self.database.initialize()
        integrity = self.database.validate_fts_integrity()
        documents = self.repository.list_all()
        total = len(documents)

        missing_field_counts: dict[str, int] = {
            field: 0 for field in _RICH_FIELDS + _IDENTITY_FIELDS
        }

        for document in documents:
            for field in missing_field_counts:
                value = document.get(field)
                if value is None or not str(value).strip():
                    missing_field_counts[field] += 1

        missing_rates = {
            field: (
                count / float(total) if total else 0.0
            )
            for field, count in missing_field_counts.items()
        }

        identifier_coverage = {
            "drawing_number": 1.0 - missing_rates["drawing_number"],
            "part_numbers": 1.0 - missing_rates["part_numbers"],
            "material": 1.0 - missing_rates["material"],
            "revision": 1.0 - missing_rates["revision"],
        }

        return {
            "document_count": total,
            "fts_integrity": integrity,
            "missing_field_counts": missing_field_counts,
            "missing_field_rates": missing_rates,
            "identifier_coverage": identifier_coverage,
            "ok": bool(integrity.get("ok")),
        }
