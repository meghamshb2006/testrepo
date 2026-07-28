from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from search.database import SearchDatabase
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository
from search.services.bulk_ingestion_service import BulkIngestionService


def test_seed_and_count_via_bulk_documents(tmp_path: Path) -> None:
    database = SearchDatabase(str(tmp_path / "dataset.db"))
    database.initialize()
    repository = SearchRepository(database)
    now = datetime.now(timezone.utc)

    report = BulkIngestionService(repository=repository).ingest_documents(
        [
            SearchDocument(
                drawing_id="drawing-001",
                filename="a.pdf",
                drawing_number="DR-1001",
                searchable_text="DR-1001 aluminium",
                created_at=now,
                updated_at=now,
            )
        ]
    )

    assert report.succeeded == 1
    assert repository.count() == 1
    assert repository.get_by_drawing_id("drawing-001") is not None
    database.close()


def test_golden_seed_pack_loads(tmp_path: Path) -> None:
    seed_path = (
        Path(__file__).resolve().parents[2]
        / "evaluation"
        / "datasets"
        / "golden_seed_documents.json"
    )
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    documents = [
        SearchDocument.model_validate(item)
        for item in payload["documents"]
    ]

    database = SearchDatabase(str(tmp_path / "golden.db"))
    database.initialize()
    repository = SearchRepository(database)
    report = BulkIngestionService(repository=repository).ingest_documents(
        documents
    )

    assert report.succeeded == 3
    assert repository.count() == 3
    database.close()
