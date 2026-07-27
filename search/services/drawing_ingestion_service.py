from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any

import fitz

from search.models.drawing_analysis import DrawingAnalysis
from search.repositories.search_repository import SearchRepository
from search.services.kimi_client import KimiClient
from search.services.search_document_builder import SearchDocumentBuilder


class DrawingIngestionService:
    """
    Ingests an engineering drawing PDF.

    Pipeline:
    PDF
    -> render pages as PNG images
    -> analyse each page with Kimi Vision
    -> validate each response as DrawingAnalysis
    -> merge page analyses
    -> build SearchDocument
    -> store in SQLite
    """

    ANALYSIS_PROMPT = """
Analyse this engineering drawing page.

Return one valid JSON object only.

Use this structure:

{
  "drawing_number": null,
  "revision": null,
  "title": null,
  "material": null,
  "part_numbers": [],
  "dimensions": [],
  "tolerances": [],
  "notes": [],
  "analysis_version": "1.0"
}

Rules:
- Do not invent values.
- Use null when a single value is not visible.
- Use an empty list when a list value is not visible.
- Preserve engineering identifiers exactly.
- Preserve dimensions, units, tolerances, materials, part numbers,
  drawing numbers, revision codes, standards, and manufacturing notes.
- Return JSON only.
""".strip()

    def __init__(
        self,
        repository: SearchRepository,
        kimi_client: KimiClient,
        builder: SearchDocumentBuilder | None = None,
        render_scale: float = 2.0,
    ) -> None:
        if render_scale <= 0:
            raise ValueError("render_scale must be greater than zero.")

        self.repository = repository
        self.kimi_client = kimi_client
        self.builder = builder or SearchDocumentBuilder()
        self.render_scale = render_scale

    @staticmethod
    def _create_drawing_id(pdf_path: Path) -> str:
        file_bytes = pdf_path.read_bytes()
        digest = hashlib.sha256(file_bytes).hexdigest()
        return f"drawing-{digest[:16]}"

    def _render_pdf_pages(self, pdf_path: Path) -> list[str]:
        document = fitz.open(pdf_path)

        try:
            if document.page_count == 0:
                raise ValueError("The PDF contains no pages.")

            encoded_pages: list[str] = []

            matrix = fitz.Matrix(
                self.render_scale,
                self.render_scale,
            )

            for page_number in range(document.page_count):
                page = document.load_page(page_number)

                pixmap = page.get_pixmap(
                    matrix=matrix,
                    alpha=False,
                )

                image_bytes = pixmap.tobytes("png")

                encoded_pages.append(
                    base64.b64encode(image_bytes).decode("ascii")
                )

            return encoded_pages

        finally:
            document.close()

    @staticmethod
    def _first_non_empty_value(
        page_analyses: list[DrawingAnalysis],
        field_names: list[str],
    ) -> Any:
        for analysis in page_analyses:
            for field_name in field_names:
                value = getattr(analysis, field_name, None)

                if value is None:
                    continue

                if isinstance(value, str) and not value.strip():
                    continue

                if isinstance(value, list) and not value:
                    continue

                return value

        return None

    @staticmethod
    def _merge_unique_list_values(
        page_analyses: list[DrawingAnalysis],
        field_name: str,
    ) -> list[str]:
        merged_values: list[str] = []
        seen: set[str] = set()

        for analysis in page_analyses:
            values = getattr(analysis, field_name, [])

            if not isinstance(values, list):
                values = [values]

            for value in values:
                value_text = str(value).strip()

                if not value_text:
                    continue

                normalised = value_text.casefold()

                if normalised in seen:
                    continue

                seen.add(normalised)
                merged_values.append(value_text)

        return merged_values

    def _merge_page_analyses(
        self,
        page_analyses: list[DrawingAnalysis],
    ) -> DrawingAnalysis:
        if not page_analyses:
            raise ValueError("No page analyses were returned by Kimi.")

        return DrawingAnalysis(
            drawing_number=self._first_non_empty_value(
                page_analyses,
                ["drawing_number"],
            ),
            revision=self._first_non_empty_value(
                page_analyses,
                ["revision"],
            ),
            title=self._first_non_empty_value(
                page_analyses,
                ["title"],
            ),
            material=self._first_non_empty_value(
                page_analyses,
                ["material"],
            ),
            part_numbers=self._merge_unique_list_values(
                page_analyses,
                "part_numbers",
            ),
            dimensions=self._merge_unique_list_values(
                page_analyses,
                "dimensions",
            ),
            tolerances=self._merge_unique_list_values(
                page_analyses,
                "tolerances",
            ),
            notes=self._merge_unique_list_values(
                page_analyses,
                "notes",
            ),
            page_analyses=[
                analysis.model_dump(mode="json")
                for analysis in page_analyses
            ],
            analysis_version="1.0",
        )

    def ingest_pdf(
        self,
        pdf_path: str | Path,
    ) -> dict[str, Any]:
        resolved_path = Path(pdf_path).expanduser().resolve()

        if not resolved_path.exists():
            raise FileNotFoundError(
                f"PDF file was not found: {resolved_path}"
            )

        if not resolved_path.is_file():
            raise ValueError(
                f"Path is not a file: {resolved_path}"
            )

        if resolved_path.suffix.lower() != ".pdf":
            raise ValueError(
                "Drawing ingestion currently supports PDF files only."
            )

        drawing_id = self._create_drawing_id(resolved_path)
        encoded_pages = self._render_pdf_pages(resolved_path)

        page_analyses: list[DrawingAnalysis] = []

        for page_index, encoded_page in enumerate(
            encoded_pages,
            start=1,
        ):
            page_prompt = (
                f"{self.ANALYSIS_PROMPT}\n\n"
                f"This image is page {page_index} "
                f"of {len(encoded_pages)}."
            )

            raw_analysis = self.kimi_client.analyse_image(
                image_base64=encoded_page,
                prompt=page_prompt,
            )

            if not isinstance(raw_analysis, dict):
                raise TypeError(
                    f"Kimi returned a non-object result for page "
                    f"{page_index}."
                )

            raw_analysis["page_number"] = page_index

            try:
                validated_analysis = DrawingAnalysis.model_validate(
                    raw_analysis
                )
            except Exception as exc:
                raise ValueError(
                    f"Kimi returned invalid drawing analysis data "
                    f"for page {page_index}: {exc}"
                ) from exc

            page_analyses.append(validated_analysis)

        merged_analysis = self._merge_page_analyses(
            page_analyses
        )

        search_document = self.builder.build(
            drawing_id=drawing_id,
            filename=resolved_path.name,
            analysis=merged_analysis.model_dump(mode="python"),
        )

        self.repository.upsert(search_document)

        return {
            "drawing_id": drawing_id,
            "filename": resolved_path.name,
            "page_count": len(encoded_pages),
            "analysis": merged_analysis.model_dump(mode="json"),
            "search_document": search_document.model_dump(
                mode="json"
            ),
        }
