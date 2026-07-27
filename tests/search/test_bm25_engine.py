from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas import (
    Dimension,
    DrawingAnalysis,
    DrawingMetadata,
)
from search.database import SearchDatabase
from search.engines.bm25_engine import BM25SearchEngine
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository
from search.services.nltk_processor import NLTKProcessor
from search.services.search_document_builder import SearchDocumentBuilder


def _build_document(
    builder: SearchDocumentBuilder,
    drawing_id: str,
    filename: str,
    analysis: DrawingAnalysis,
) -> SearchDocument:
    return builder.build(
        drawing_id=drawing_id,
        filename=filename,
        analysis=analysis,
    )


@pytest.fixture
def bm25_setup(tmp_path: Path) -> tuple[SearchRepository, BM25SearchEngine]:
    db_path = tmp_path / "test_bm25_search.db"
    database = SearchDatabase(str(db_path))
    database.initialize()
    repository = SearchRepository(database)
    builder = SearchDocumentBuilder()

    documents = [
        _build_document(
            builder,
            "drawing-001",
            "aluminium_mounting_bracket.pdf",
            DrawingAnalysis(
                metadata=DrawingMetadata(
                    drawing_number="DR-1001",
                    revision="C",
                    title="Aluminium Mounting Bracket",
                    material="Aluminium 6061-T6",
                ),
                dimensions=[
                    Dimension(value="Length 120 mm"),
                    Dimension(value="Hole diameter 10.5 mm"),
                ],
                general_tolerances=["General tolerance plusminus 0.05 mm"],
                manufacturing_notes=["Surface finish anodized"],
            ),
        ),
        _build_document(
            builder,
            "drawing-002",
            "stainless_motor_housing.pdf",
            DrawingAnalysis(
                metadata=DrawingMetadata(
                    drawing_number="DR-2002",
                    title="Stainless Steel Motor Housing",
                    material="Stainless Steel 316",
                ),
                dimensions=[Dimension(value="Outer diameter 150 mm")],
                manufacturing_notes=["Machine all critical surfaces"],
            ),
        ),
        _build_document(
            builder,
            "drawing-003",
            "copper_busbar.pdf",
            DrawingAnalysis(
                metadata=DrawingMetadata(
                    drawing_number="DR-3003",
                    title="Electrical Copper Busbar",
                    material="Copper C110",
                ),
                dimensions=[Dimension(value="Length 300 mm")],
            ),
        ),
    ]

    for document in documents:
        repository.upsert(document)

    engine = BM25SearchEngine(
        repository=repository,
        processor=NLTKProcessor(),
    )
    engine.build_index()

    yield repository, engine

    database.close()


def test_bm25_ranks_aluminium_bracket_first(
    bm25_setup: tuple[SearchRepository, BM25SearchEngine],
) -> None:
    _repository, engine = bm25_setup

    results = engine.search(
        query="aluminium 6061-T6 bracket with 10.5 mm hole",
        top_k=3,
    )

    assert results
    assert results[0]["drawing_id"] == "drawing-001"
    assert results[0]["bm25_score"] > 0
    assert "6061-t6" in results[0]["matched_terms"] or "aluminium" in results[0]["matched_terms"]


def test_empty_query_raises(
    bm25_setup: tuple[SearchRepository, BM25SearchEngine],
) -> None:
    _repository, engine = bm25_setup

    with pytest.raises(ValueError, match="empty"):
        engine.search("")
