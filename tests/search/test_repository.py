from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from search.database import SearchDatabase
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository


@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_drawing_search.db"


@pytest.fixture
def repository(test_db_path: Path) -> SearchRepository:
    database = SearchDatabase(str(test_db_path))
    database.initialize()
    repo = SearchRepository(database)
    yield repo
    database.close()


@pytest.fixture
def sample_document() -> SearchDocument:
    now = datetime.now(timezone.utc)

    return SearchDocument(
        drawing_id="drawing-001",
        filename="mounting_bracket.pdf",
        drawing_number="DR-1023",
        revision="C",
        title="Mounting Bracket",
        material="Aluminium 6061-T6",
        finish="Anodised",
        units="mm",
        part_numbers="BR-1001",
        dimensions_text="120 mm 80 mm hole diameter 10 mm",
        tolerances_text="ISO-2768-mK plusminus 0.05 mm",
        notes_text="Surface finish anodised. Deburr all edges.",
        searchable_text=(
            "DR-1023 mounting bracket aluminium 6061-T6 BR-1001 "
            "120 mm ISO-2768-mK plusminus 0.05 mm anodised revision C"
        ),
        analysis_version="1.0",
        created_at=now,
        updated_at=now,
    )


def test_upsert_and_get(
    repository: SearchRepository,
    sample_document: SearchDocument,
) -> None:
    repository.upsert(sample_document)

    stored = repository.get_by_drawing_id("drawing-001")

    assert stored is not None
    assert stored["filename"] == "mounting_bracket.pdf"
    assert stored["material"] == "Aluminium 6061-T6"
    assert repository.count() == 1


def test_fts_search(
    repository: SearchRepository,
    sample_document: SearchDocument,
) -> None:
    repository.upsert(sample_document)

    results = repository.search_fts("aluminium AND bracket")

    assert len(results) == 1
    assert results[0]["drawing_id"] == "drawing-001"


def test_delete_and_cleanup(
    repository: SearchRepository,
    sample_document: SearchDocument,
) -> None:
    repository.upsert(sample_document)

    deleted = repository.delete("drawing-001")

    assert deleted is True
    assert repository.count() == 0
    assert repository.get_by_drawing_id("drawing-001") is None

    fts_results = repository.search_fts("aluminium")
    assert fts_results == []
