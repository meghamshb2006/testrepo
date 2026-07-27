from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from search.context.context_builder import ContextBuilder
from search.database import SearchDatabase
from search.engines.bm25_engine import BM25SearchEngine
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository
from search.services.retrieval_service import RetrievalService


@pytest.fixture
def retrieval_setup(tmp_path: Path) -> RetrievalService:
    database = SearchDatabase(str(tmp_path / "retrieval.db"))
    database.initialize()
    repository = SearchRepository(database)

    now = datetime.now(timezone.utc)
    documents = [
        SearchDocument(
            drawing_id="drawing-001",
            filename="mounting_bracket.pdf",
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
            searchable_text=(
                "DR-1023 mounting bracket aluminium 6061-T6 BR-1001 "
                "120 mm ISO-2768-mK plusminus 0.05 mm anodised revision C"
            ),
            created_at=now,
            updated_at=now,
        ),
        SearchDocument(
            drawing_id="drawing-002",
            filename="motor_housing.pdf",
            drawing_number="DR-2048",
            title="Motor Housing",
            material="Stainless Steel 316",
            searchable_text=(
                "DR-2048 motor housing stainless steel 316 "
                "machine critical surfaces"
            ),
            created_at=now,
            updated_at=now,
        ),
    ]

    for document in documents:
        repository.upsert(document)

    service = RetrievalService(repository=repository)

    yield service

    database.close()


def test_retrieve_returns_bm25_ranked_results(
    retrieval_setup: RetrievalService,
) -> None:
    response = retrieval_setup.retrieve(
        query="aluminium 6061-T6 bracket",
        candidate_limit=10,
        top_k=2,
    )

    assert response["query"] == "aluminium 6061-T6 bracket"
    assert response["candidate_count"] >= 1
    assert response["result_count"] >= 1
    assert response["results"][0]["drawing_id"] == "drawing-001"
    assert response["results"][0]["rank"] == 1
    assert "bm25_score" in response["results"][0]
    assert response["context"]


def test_retrieve_empty_fts_result(
    retrieval_setup: RetrievalService,
) -> None:
    response = retrieval_setup.retrieve(
        query="nonexistent titanium widget",
        candidate_limit=10,
        top_k=3,
    )

    assert response == {
        "query": "nonexistent titanium widget",
        "candidate_count": 0,
        "result_count": 0,
        "results": [],
        "context": "",
    }


def test_retrieve_invalid_query_raises(
    retrieval_setup: RetrievalService,
) -> None:
    with pytest.raises(ValueError, match="blank"):
        retrieval_setup.retrieve("   ")


def test_retrieve_top_k_exceeds_candidate_limit_raises(
    retrieval_setup: RetrievalService,
) -> None:
    with pytest.raises(ValueError, match="top_k must not exceed"):
        retrieval_setup.retrieve(
            query="aluminium",
            candidate_limit=2,
            top_k=5,
        )


def test_retrieve_honours_max_context_characters(
    retrieval_setup: RetrievalService,
) -> None:
    response = retrieval_setup.retrieve(
        query="aluminium bracket",
        candidate_limit=10,
        top_k=2,
        max_context_characters=500,
    )

    assert response["context"]
    assert len(response["context"]) <= 500


def test_retrieve_passes_fts_candidates_to_bm25() -> None:
    candidate = {
        "drawing_id": "drawing-001",
        "filename": "mounting_bracket.pdf",
        "searchable_text": "aluminium 6061-T6 bracket",
        "fts_score": -1.5,
    }

    repository = MagicMock()
    repository.search_fts.return_value = [candidate]

    bm25_engine = MagicMock()
    bm25_engine.search.return_value = [
        {
            "rank": 1,
            "drawing_id": "drawing-001",
            "filename": "mounting_bracket.pdf",
            "searchable_text": "aluminium 6061-T6 bracket",
            "bm25_score": 2.5,
            "matched_terms": ["aluminium"],
        }
    ]

    context_builder = MagicMock()
    context_builder.build_context.return_value = "structured context"

    service = RetrievalService(
        repository=repository,
        bm25_engine=bm25_engine,
        context_builder=context_builder,
    )

    response = service.retrieve("aluminium", candidate_limit=10, top_k=1)

    repository.search_fts.assert_called_once_with("aluminium", limit=10)
    bm25_engine.build_index.assert_called_once_with([candidate])
    bm25_engine.search.assert_called_once_with("aluminium", top_k=1)
    context_builder.build_context.assert_called_once()

    assert response["candidate_count"] == 1
    assert response["result_count"] == 1
    assert response["context"] == "structured context"
