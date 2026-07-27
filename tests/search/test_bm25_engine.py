from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

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
                    finish="Anodised",
                    units="mm",
                ),
                dimensions=[
                    Dimension(value="Length 120 mm"),
                    Dimension(value="Hole diameter 10.5 mm"),
                ],
                general_tolerances=["ISO-2768-mK"],
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


def test_build_index_accepts_supplied_candidates(
    bm25_setup: tuple[SearchRepository, BM25SearchEngine],
) -> None:
    repository, engine = bm25_setup

    candidates = repository.search_fts("aluminium", limit=5)
    assert candidates

    engine.build_index(candidates)
    results = engine.search("aluminium 6061-T6", top_k=1)

    assert results[0]["drawing_id"] == "drawing-001"
    assert results[0]["revision"] == "C"
    assert results[0]["finish"] == "Anodised"
    assert results[0]["units"] == "mm"
    assert results[0]["dimensions_text"]
    assert results[0]["tolerances_text"]
    assert results[0]["notes_text"]


def test_supplied_candidates_do_not_load_unrelated_rows(
    bm25_setup: tuple[SearchRepository, BM25SearchEngine],
) -> None:
    repository, engine = bm25_setup

    candidates = repository.search_fts("aluminium", limit=5)
    engine.build_index(candidates)

    results = engine.search("copper busbar", top_k=5)

    assert results == []


def test_result_preserves_fts_score(
    bm25_setup: tuple[SearchRepository, BM25SearchEngine],
) -> None:
    repository, engine = bm25_setup

    candidates = repository.search_fts("aluminium", limit=5)
    engine.build_index(candidates)

    results = engine.search("aluminium", top_k=1)

    assert "fts_score" in results[0]
    assert results[0]["fts_score"] == candidates[0]["fts_score"]


def test_engineering_identifiers_remain_matched(
    bm25_setup: tuple[SearchRepository, BM25SearchEngine],
) -> None:
    repository, engine = bm25_setup

    candidates = repository.search_fts("6061-T6 OR ISO-2768 OR BR-1001", limit=5)
    engine.build_index(candidates)

    results = engine.search(
        "6061-T6 ISO-2768 BR-1001 aluminium bracket",
        top_k=3,
    )

    drawing_001 = next(
        result for result in results if result["drawing_id"] == "drawing-001"
    )
    matched = set(drawing_001["matched_terms"])

    assert "6061-t6" in matched
    assert "iso-2768" in matched


def test_empty_candidate_list_raises(
    bm25_setup: tuple[SearchRepository, BM25SearchEngine],
) -> None:
    _repository, engine = bm25_setup

    with pytest.raises(ValueError, match="no documents"):
        engine.build_index([])


def test_candidates_with_no_searchable_text_are_skipped(
    tmp_path: Path,
) -> None:
    database = SearchDatabase(str(tmp_path / "empty_text.db"))
    database.initialize()
    repository = SearchRepository(database)
    engine = BM25SearchEngine(repository=repository)

    now = datetime.now(timezone.utc)
    repository.upsert(
        SearchDocument(
            drawing_id="drawing-empty",
            filename="empty.pdf",
            searchable_text="placeholder aluminium bracket",
            created_at=now,
            updated_at=now,
        )
    )

    candidates = [
        {
            "drawing_id": "drawing-empty",
            "filename": "empty.pdf",
            "searchable_text": "   ",
        }
    ]

    with pytest.raises(ValueError, match="searchable text"):
        engine.build_index(candidates)

    database.close()
