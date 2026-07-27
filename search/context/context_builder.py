from typing import Any


class ContextBuilder:
    """Builds retrieval context from ranked search results."""

    @staticmethod
    def build_context(
        results: list[dict[str, Any]],
        max_documents: int = 5,
    ) -> str:
        if not results:
            return ""

        sections: list[str] = []

        for result in results[:max_documents]:
            drawing_number = result.get("drawing_number") or "unknown"
            title = result.get("title") or result.get("filename") or "untitled"
            material = result.get("material") or ""
            searchable_text = result.get("searchable_text") or ""

            section_lines = [
                f"Drawing: {drawing_number} - {title}",
            ]

            if material:
                section_lines.append(f"Material: {material}")

            if searchable_text:
                section_lines.append(searchable_text)

            sections.append("\n".join(section_lines))

        return "\n\n---\n\n".join(sections)
