from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from search.models.search_document import SearchDocument
from search.services.bulk_ingestion_service import BulkIngestionService


def test_discover_pdfs(tmp_path: Path) -> None:
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "b.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "ignore.txt").write_text("x", encoding="utf-8")

    repository = MagicMock()
    service = BulkIngestionService(repository=repository)
    pdfs = service.discover_pdfs(tmp_path, recursive=True)

    assert len(pdfs) == 2
    assert {path.name for path in pdfs} == {"a.pdf", "b.pdf"}


def test_ingest_directory_continues_on_error(tmp_path: Path) -> None:
    (tmp_path / "ok.pdf").write_bytes(b"%PDF-ok")
    (tmp_path / "bad.pdf").write_bytes(b"%PDF-bad")

    repository = MagicMock()
    repository.get_by_drawing_id.return_value = None

    ingestion = MagicMock()

    def _ingest(path: Path):
        if path.name == "bad.pdf":
            raise RuntimeError("boom")
        return {
            "drawing_id": "drawing-ok",
            "filename": path.name,
            "page_count": 1,
        }

    ingestion.ingest_pdf.side_effect = _ingest

    service = BulkIngestionService(
        repository=repository,
        ingestion_service=ingestion,
    )
    report = service.ingest_directory(
        tmp_path,
        recursive=False,
        continue_on_error=True,
    )

    assert report.total_files == 2
    assert report.succeeded == 1
    assert report.failed == 1
    assert len(report.errors) == 1


def test_ingest_documents_upserts(tmp_path: Path) -> None:
    repository = MagicMock()
    repository.get_by_drawing_id.return_value = None
    service = BulkIngestionService(repository=repository)
    now = datetime.now(timezone.utc)
    documents = [
        SearchDocument(
            drawing_id="drawing-001",
            filename="a.pdf",
            searchable_text="DR-1001 aluminium",
            created_at=now,
            updated_at=now,
        )
    ]

    report = service.ingest_documents(documents)

    assert report.succeeded == 1
    repository.upsert.assert_called_once()
