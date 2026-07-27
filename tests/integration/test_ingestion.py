from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.schemas import (
    Dimension,
    DrawingAnalysis,
    DrawingMetadata,
)
from search.database import SearchDatabase
from search.repositories.search_repository import SearchRepository
from search.services.drawing_ingestion_service import DrawingIngestionService
from search.services.search_document_builder import SearchDocumentBuilder


@pytest.fixture
def ingestion_setup(tmp_path: Path) -> tuple[DrawingIngestionService, SearchRepository, Path]:
    db_path = tmp_path / "test_ingestion.db"
    database = SearchDatabase(str(db_path))
    database.initialize()
    repository = SearchRepository(database)

    mock_analyzer = MagicMock()
    mock_analyzer.analyze.return_value = DrawingAnalysis(
        metadata=DrawingMetadata(
            drawing_number="DR-2048",
            revision="B",
            title="Motor Housing",
            material="Stainless Steel 316",
        ),
        dimensions=[
            Dimension(value="Outer diameter 150 mm"),
            Dimension(value="Inner diameter 120 mm"),
        ],
        general_tolerances=["plusminus 0.1 mm"],
        manufacturing_notes=[
            "Machine all critical surfaces",
            "Remove sharp edges",
        ],
    )

    service = DrawingIngestionService(
        repository=repository,
        analyzer=mock_analyzer,
        builder=SearchDocumentBuilder(),
    )

    pdf_path = tmp_path / "motor_housing.pdf"

    yield service, repository, pdf_path

    database.close()


def test_ingestion_with_mocked_analyser(
    ingestion_setup: tuple[DrawingIngestionService, SearchRepository, Path],
) -> None:
    service, repository, pdf_path = ingestion_setup

    # Minimal valid PDF for pymupdf rendering
    import pymupdf

    doc = pymupdf.open()
    doc.new_page(width=200, height=200)
    doc.save(str(pdf_path))
    doc.close()

    result = service.ingest_pdf(pdf_path)

    assert result["filename"] == "motor_housing.pdf"
    assert result["page_count"] >= 1

    stored = repository.get_by_drawing_id(result["drawing_id"])

    assert stored is not None
    assert stored["drawing_number"] == "DR-2048"
    assert stored["material"] == "Stainless Steel 316"

    fts_results = repository.search_fts("stainless AND housing")
    assert len(fts_results) == 1
    assert fts_results[0]["drawing_id"] == result["drawing_id"]
