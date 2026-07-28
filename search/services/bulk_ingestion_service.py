"""Bulk ingestion of engineering drawing PDFs into the search index."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository
from search.services.drawing_ingestion_service import DrawingIngestionService


@dataclass
class BulkIngestResult:
    total_files: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_files": self.total_files,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "results": self.results,
            "errors": self.errors,
        }


class BulkIngestionService:
    """Ingest many PDFs (or prebuilt SearchDocuments) without changing retrieval."""

    def __init__(
        self,
        repository: SearchRepository,
        ingestion_service: DrawingIngestionService | None = None,
    ) -> None:
        self.repository = repository
        self._ingestion_service = ingestion_service

    @property
    def ingestion_service(self) -> DrawingIngestionService:
        if self._ingestion_service is None:
            self._ingestion_service = DrawingIngestionService(
                repository=self.repository,
            )
        return self._ingestion_service

    @staticmethod
    def discover_pdfs(
        source_dir: str | Path,
        *,
        recursive: bool = True,
    ) -> list[Path]:
        root = Path(source_dir).expanduser().resolve()

        if not root.exists():
            raise FileNotFoundError(f"Source directory was not found: {root}")

        if not root.is_dir():
            raise ValueError(f"Source path is not a directory: {root}")

        pattern = "**/*.pdf" if recursive else "*.pdf"
        return sorted(path for path in root.glob(pattern) if path.is_file())

    def ingest_directory(
        self,
        source_dir: str | Path,
        *,
        recursive: bool = True,
        continue_on_error: bool = True,
        skip_existing: bool = False,
        limit: int | None = None,
        progress_callback: Callable[[int, int, Path], None] | None = None,
    ) -> BulkIngestResult:
        pdfs = self.discover_pdfs(source_dir, recursive=recursive)

        if limit is not None:
            if limit < 1:
                raise ValueError("limit must be >= 1 when provided.")
            pdfs = pdfs[:limit]

        report = BulkIngestResult(total_files=len(pdfs))
        started = time.perf_counter()

        for index, pdf_path in enumerate(pdfs, start=1):
            if progress_callback is not None:
                progress_callback(index, len(pdfs), pdf_path)

            drawing_id = DrawingIngestionService._create_drawing_id(pdf_path)

            if skip_existing and self.repository.get_by_drawing_id(drawing_id):
                report.skipped += 1
                report.results.append(
                    {
                        "status": "skipped",
                        "path": str(pdf_path),
                        "drawing_id": drawing_id,
                        "reason": "already_indexed",
                    }
                )
                continue

            try:
                result = self.ingestion_service.ingest_pdf(pdf_path)
                report.succeeded += 1
                report.results.append(
                    {
                        "status": "succeeded",
                        "path": str(pdf_path),
                        "drawing_id": result["drawing_id"],
                        "filename": result["filename"],
                        "page_count": result["page_count"],
                    }
                )
            except Exception as exc:
                report.failed += 1
                error_entry = {
                    "status": "failed",
                    "path": str(pdf_path),
                    "drawing_id": drawing_id,
                    "error": str(exc),
                }
                report.errors.append(error_entry)
                report.results.append(error_entry)

                if not continue_on_error:
                    break

        report.elapsed_ms = (time.perf_counter() - started) * 1000.0
        return report

    def ingest_documents(
        self,
        documents: list[SearchDocument],
        *,
        skip_existing: bool = False,
    ) -> BulkIngestResult:
        """Upsert prebuilt SearchDocuments (offline / golden pack seeding)."""
        report = BulkIngestResult(total_files=len(documents))
        started = time.perf_counter()

        for document in documents:
            if skip_existing and self.repository.get_by_drawing_id(
                document.drawing_id
            ):
                report.skipped += 1
                report.results.append(
                    {
                        "status": "skipped",
                        "drawing_id": document.drawing_id,
                        "filename": document.filename,
                        "reason": "already_indexed",
                    }
                )
                continue

            try:
                self.repository.upsert(document)
                report.succeeded += 1
                report.results.append(
                    {
                        "status": "succeeded",
                        "drawing_id": document.drawing_id,
                        "filename": document.filename,
                    }
                )
            except Exception as exc:
                report.failed += 1
                error_entry = {
                    "status": "failed",
                    "drawing_id": document.drawing_id,
                    "filename": document.filename,
                    "error": str(exc),
                }
                report.errors.append(error_entry)
                report.results.append(error_entry)

        report.elapsed_ms = (time.perf_counter() - started) * 1000.0
        return report
