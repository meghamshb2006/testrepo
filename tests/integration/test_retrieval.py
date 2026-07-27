from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from search.database import SearchDatabase
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository
from search.services.retrieval_service import RetrievalService


@pytest.fixture
def retrieval_service(tmp_path: Path) -> RetrievalService:
    database = SearchDatabase(str(tmp_path / "integration_retrieval.db"))
    database.initialize()
    repository = SearchRepository(database)

    now = datetime.now(timezone.utc)
    documents = [
        SearchDocument(
            drawing_id="drawing-001",
            filename="aluminium_mounting_bracket.pdf",
            drawing_number="DR-1001",
            revision="C",
            title="Aluminium Mounting Bracket",
            material="Aluminium 6061-T6",
            finish="Anodised",
            units="mm",
            part_numbers="BR-1001",
            dimensions_text="Length 120 mm Hole diameter 10.5 mm",
            tolerances_text="ISO-2768-mK plusminus 0.05 mm",
            notes_text="Surface finish anodized",
            searchable_text=(
                "DR-1001 aluminium mounting bracket 6061-T6 BR-1001 "
                "120 mm 10.5 mm ISO-2768-mK anodised"
            ),
            created_at=now,
            updated_at=now,
        ),
        SearchDocument(
            drawing_id="drawing-002",
            filename="stainless_motor_housing.pdf",
            drawing_number="DR-2002",
            title="Stainless Steel Motor Housing",
            material="Stainless Steel 316",
            searchable_text=(
                "DR-2002 stainless steel motor housing machine surfaces"
            ),
            created_at=now,
            updated_at=now,
        ),
        SearchDocument(
            drawing_id="drawing-003",
            filename="copper_busbar.pdf",
            drawing_number="DR-3003",
            title="Electrical Copper Busbar",
            material="Copper C110",
            searchable_text="DR-3003 copper busbar tin plated electrical",
            created_at=now,
            updated_at=now,
        ),
    ]

    for document in documents:
        repository.upsert(document)

    service = RetrievalService(repository=repository)

    yield service

    database.close()


def test_two_stage_retrieval_integration(
    retrieval_service: RetrievalService,
) -> None:
    response = retrieval_service.retrieve(
        query="aluminium 6061-T6 bracket 10.5 mm",
        candidate_limit=5,
        top_k=2,
    )

    assert response["candidate_count"] >= 1
    assert response["result_count"] >= 1
    assert response["results"][0]["drawing_id"] == "drawing-001"
    assert response["results"][0]["material"] == "Aluminium 6061-T6"
    assert response["results"][0]["finish"] == "Anodised"
    assert "fts_score" in response["results"][0]
    assert "Retrieved Drawing 1" in response["context"]
    assert "6061-T6" in response["context"] or "6061-t6" in response["context"].lower()
