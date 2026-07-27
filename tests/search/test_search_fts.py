from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from search.database import SearchDatabase
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository


EXPECTED_DOCUMENT_FIELDS = {
    "drawing_id",
    "filename",
    "drawing_number",
    "revision",
    "title",
    "material",
    "finish",
    "units",
    "part_numbers",
    "dimensions_text",
    "tolerances_text",
    "notes_text",
    "searchable_text",
    "analysis_version",
    "created_at",
    "updated_at",
}


@pytest.fixture
def repository(tmp_path: Path) -> SearchRepository:
    database = SearchDatabase(str(tmp_path / "fts_search.db"))
    database.initialize()
    repo = SearchRepository(database)
    yield repo
    database.close()


def _make_document(
    drawing_id: str,
    filename: str,
    searchable_text: str,
    **fields: str,
) -> SearchDocument:
    now = datetime.now(timezone.utc)

    return SearchDocument(
        drawing_id=drawing_id,
        filename=filename,
        drawing_number=fields.get("drawing_number"),
        revision=fields.get("revision"),
        title=fields.get("title"),
        material=fields.get("material"),
        finish=fields.get("finish"),
        units=fields.get("units"),
        part_numbers=fields.get("part_numbers", ""),
        dimensions_text=fields.get("dimensions_text", ""),
        tolerances_text=fields.get("tolerances_text", ""),
        notes_text=fields.get("notes_text", ""),
        searchable_text=searchable_text,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def indexed_documents(repository: SearchRepository) -> None:
    repository.upsert(
        _make_document(
            "drawing-001",
            "mounting_bracket.pdf",
            (
                "DR-1023 mounting bracket aluminium 6061-T6 BR-1001 "
                "120 mm ISO-2768-mK plusminus 0.05 mm anodised revision C"
            ),
            drawing_number="DR-1023",
            revision="C",
            title="Mounting Bracket",
            material="Aluminium 6061-T6",
            finish="Anodised",
            units="mm",
            part_numbers="BR-1001",
            dimensions_text="120 mm hole diameter 10 mm",
            tolerances_text="ISO-2768-mK plusminus 0.05 mm",
            notes_text="Surface finish anodised",
        )
    )
    repository.upsert(
        _make_document(
            "drawing-002",
            "motor_housing.pdf",
            (
                "DR-2048 motor housing stainless steel 316 "
                "machine critical surfaces"
            ),
            drawing_number="DR-2048",
            title="Motor Housing",
            material="Stainless Steel 316",
        )
    )
    repository.upsert(
        _make_document(
            "drawing-003",
            "copper_busbar.pdf",
            "DR-3003 copper busbar electrical component tin plated",
            drawing_number="DR-3003",
            title="Copper Busbar",
            material="Copper C110",
        )
    )


def test_search_fts_returns_full_document_fields(
    repository: SearchRepository,
    indexed_documents: None,
) -> None:
    results = repository.search_fts("aluminium AND bracket", limit=5)

    assert len(results) == 1

    result = results[0]

    assert EXPECTED_DOCUMENT_FIELDS.issubset(result.keys())
    assert "fts_score" in result
    assert result["drawing_id"] == "drawing-001"
    assert result["revision"] == "C"
    assert result["finish"] == "Anodised"
    assert result["units"] == "mm"
    assert result["dimensions_text"] == "120 mm hole diameter 10 mm"
    assert result["tolerances_text"] == "ISO-2768-mK plusminus 0.05 mm"
    assert result["notes_text"] == "Surface finish anodised"


def test_search_fts_returns_only_matching_rows(
    repository: SearchRepository,
    indexed_documents: None,
) -> None:
    results = repository.search_fts("copper AND busbar", limit=10)

    assert len(results) == 1
    assert results[0]["drawing_id"] == "drawing-003"


def test_search_fts_respects_limit(
    repository: SearchRepository,
    indexed_documents: None,
) -> None:
    results = repository.search_fts(
        "motor OR copper OR mounting",
        limit=1,
    )

    assert len(results) == 1


def test_search_fts_rejects_blank_query(
    repository: SearchRepository,
    indexed_documents: None,
) -> None:
    with pytest.raises(ValueError, match="blank"):
        repository.search_fts("   ")


def test_search_fts_quotes_hyphenated_identifiers(
    repository: SearchRepository,
    indexed_documents: None,
) -> None:
    results = repository.search_fts("6061-T6 AND bracket", limit=5)

    assert len(results) == 1
    assert results[0]["drawing_id"] == "drawing-001"


def test_search_fts_rejects_invalid_limit(
    repository: SearchRepository,
    indexed_documents: None,
) -> None:
    with pytest.raises(ValueError, match="limit"):
        repository.search_fts("aluminium", limit=0)

    with pytest.raises(TypeError, match="limit"):
        repository.search_fts("aluminium", limit="5")


def test_search_fts_quotes_decimal_dimensions(
    repository: SearchRepository,
    indexed_documents: None,
) -> None:
    results = repository.search_fts("0.05 mm", limit=5)

    assert len(results) == 1
    assert results[0]["drawing_id"] == "drawing-001"
