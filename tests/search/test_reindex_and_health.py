from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from search.database import SearchDatabase
from search.diagnostics.health_report import RetrievalHealthReport
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository
from search.services.reindex_service import ReindexService
from search.services.retrieval_service import RetrievalService


def test_reindex_and_validate(tmp_path: Path) -> None:
    database = SearchDatabase(str(tmp_path / "reindex.db"))
    database.initialize()
    repository = SearchRepository(database)
    now = datetime.now(timezone.utc)
    repository.upsert(
        SearchDocument(
            drawing_id="drawing-001",
            filename="a.pdf",
            drawing_number="DR-1023",
            searchable_text="DR-1023 aluminium",
            created_at=now,
            updated_at=now,
        )
    )

    service = ReindexService(database)
    payload = service.rebuild_index(force_fts=True)

    assert payload["rebuild"]["document_count"] == 1
    assert payload["rebuild"]["fts_count"] == 1
    assert payload["validation"]["ok"] is True
    database.close()


def test_health_report_markdown(tmp_path: Path) -> None:
    database = SearchDatabase(str(tmp_path / "health.db"))
    database.initialize()
    repository = SearchRepository(database)
    now = datetime.now(timezone.utc)
    repository.upsert(
        SearchDocument(
            drawing_id="drawing-001",
            filename="a.pdf",
            drawing_number="DR-1023",
            material="Aluminium 6061-T6",
            searchable_text="DR-1023 aluminium 6061-T6",
            created_at=now,
            updated_at=now,
        )
    )

    reindex_service = ReindexService(database)
    retrieval_service = RetrievalService(repository=repository)
    builder = RetrievalHealthReport(
        reindex_service=reindex_service,
        retrieval_service=retrieval_service,
    )
    report = builder.build(probe_query="DR-1023")
    markdown = RetrievalHealthReport.to_markdown(report)

    assert "Retrieval Health Report" in markdown
    assert "indexed drawings" in markdown
    assert report["probe"]["result_count"] >= 1
    database.close()
