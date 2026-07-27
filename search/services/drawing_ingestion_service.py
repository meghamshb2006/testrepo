from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Any

from app.analyzer import DrawingAnalyzer
from app.renderer import render_pdf
from app.schemas import DrawingAnalysis
from search.repositories.search_repository import SearchRepository
from search.services.search_document_builder import SearchDocumentBuilder


class DrawingIngestionService:
    """
    End-to-end ingestion orchestration.

    PDF -> app.renderer -> app.analyzer -> SearchDocumentBuilder
    -> SearchRepository -> drawing_search.db
    """

    def __init__(
        self,
        repository: SearchRepository,
        analyzer: DrawingAnalyzer | None = None,
        builder: SearchDocumentBuilder | None = None,
    ) -> None:
        self.repository = repository
        self.analyzer = analyzer or DrawingAnalyzer()
        self.builder = builder or SearchDocumentBuilder()

    @staticmethod
    def _create_drawing_id(pdf_path: Path) -> str:
        file_bytes = pdf_path.read_bytes()
        digest = hashlib.sha256(file_bytes).hexdigest()
        return f"drawing-{digest[:16]}"

    def ingest_pdf(self, pdf_path: str | Path) -> dict[str, Any]:
        resolved_path = Path(pdf_path).expanduser().resolve()

        if not resolved_path.exists():
            raise FileNotFoundError(
                f"PDF file was not found: {resolved_path}"
            )

        if not resolved_path.is_file():
            raise ValueError(f"Path is not a file: {resolved_path}")

        if resolved_path.suffix.lower() != ".pdf":
            raise ValueError(
                "Drawing ingestion currently supports PDF files only."
            )

        drawing_id = self._create_drawing_id(resolved_path)

        with tempfile.TemporaryDirectory(prefix="drawing_pages_") as temp_dir:
            pages_dir = Path(temp_dir)
            page_paths = render_pdf(resolved_path, pages_dir)

            if not page_paths:
                raise ValueError("The PDF did not produce any rendered pages.")

            analysis = self.analyzer.analyze(page_paths)

        search_document = self.builder.build(
            drawing_id=drawing_id,
            filename=resolved_path.name,
            analysis=analysis,
        )

        self.repository.upsert(search_document)

        return {
            "drawing_id": drawing_id,
            "filename": resolved_path.name,
            "page_count": len(page_paths),
            "analysis": analysis.model_dump(mode="json"),
            "search_document": search_document.model_dump(mode="json"),
        }
