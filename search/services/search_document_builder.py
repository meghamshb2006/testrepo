from datetime import datetime, timezone
from typing import Any

from search.models.search_document import SearchDocument


class SearchDocumentBuilder:
    """Converts drawing-analysis data into a flattened search document."""

    @staticmethod
    def _as_text(value: Any) -> str:
        if value is None:
            return ""

        if isinstance(value, str):
            return value.strip()

        if isinstance(value, (int, float, bool)):
            return str(value)

        if isinstance(value, list):
            parts = [SearchDocumentBuilder._as_text(item) for item in value]
            return " ".join(part for part in parts if part)

        if isinstance(value, dict):
            parts = []

            for key, item in value.items():
                item_text = SearchDocumentBuilder._as_text(item)

                if item_text:
                    readable_key = key.replace("_", " ")
                    parts.append(f"{readable_key} {item_text}")

            return " ".join(parts)

        return str(value).strip()

    def build(
        self,
        drawing_id: str,
        filename: str,
        analysis: dict[str, Any],
    ) -> SearchDocument:
        now = datetime.now(timezone.utc)

        drawing_number = self._as_text(
            analysis.get("drawing_number")
            or analysis.get("document_number")
        )

        revision = self._as_text(analysis.get("revision"))

        title = self._as_text(
            analysis.get("title")
            or analysis.get("drawing_title")
            or analysis.get("part_name")
        )

        material = self._as_text(analysis.get("material"))

        part_numbers = self._as_text(
            analysis.get("part_numbers")
            or analysis.get("parts")
            or analysis.get("bill_of_materials")
            or analysis.get("bom")
        )

        dimensions_text = self._as_text(
            analysis.get("dimensions")
            or analysis.get("measurements")
        )

        tolerances_text = self._as_text(
            analysis.get("tolerances")
            or analysis.get("general_tolerance")
        )

        notes_text = self._as_text(
            analysis.get("notes")
            or analysis.get("manufacturing_notes")
            or analysis.get("technical_notes")
        )

        searchable_sections = [
            filename,
            drawing_number,
            revision,
            title,
            material,
            part_numbers,
            dimensions_text,
            tolerances_text,
            notes_text,
        ]

        searchable_text = " ".join(
            section.strip()
            for section in searchable_sections
            if section and section.strip()
        )

        if not searchable_text:
            raise ValueError(
                "Cannot build a search document from an empty analysis."
            )

        return SearchDocument(
            drawing_id=drawing_id,
            filename=filename,
            drawing_number=drawing_number or None,
            revision=revision or None,
            title=title or None,
            material=material or None,
            part_numbers=part_numbers,
            dimensions_text=dimensions_text,
            tolerances_text=tolerances_text,
            notes_text=notes_text,
            searchable_text=searchable_text,
            analysis_version=self._as_text(
                analysis.get("analysis_version")
            ) or "1.0",
            created_at=now,
            updated_at=now,
        )
