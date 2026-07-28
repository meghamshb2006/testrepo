from __future__ import annotations

from typing import Any


class ContextBuilder:
    """Builds structured retrieval context from ranked search results."""

    @staticmethod
    def _clean_value(value: Any) -> str:
        if value is None:
            return ""

        if isinstance(value, str):
            return value.strip()

        if isinstance(value, (list, tuple, set)):
            return " ".join(
                str(item).strip()
                for item in value
                if item is not None and str(item).strip()
            )

        return str(value).strip()

    @classmethod
    def _add_field(
        cls,
        lines: list[str],
        seen_values: set[str],
        label: str,
        value: Any,
    ) -> None:
        cleaned_value = cls._clean_value(value)

        if not cleaned_value:
            return

        dedupe_key = cleaned_value.casefold()

        if dedupe_key in seen_values:
            return

        seen_values.add(dedupe_key)
        lines.append(f"{label}: {cleaned_value}")

    @classmethod
    def _build_document_section(
        cls,
        result: dict[str, Any],
        position: int,
    ) -> str:
        lines: list[str] = [f"Retrieved Drawing {position}"]
        seen_values: set[str] = set()

        # Identity
        cls._add_field(
            lines, seen_values, "Drawing ID", result.get("drawing_id")
        )
        cls._add_field(
            lines, seen_values, "Filename", result.get("filename")
        )
        cls._add_field(
            lines,
            seen_values,
            "Drawing Number",
            result.get("drawing_number"),
        )
        cls._add_field(
            lines, seen_values, "Revision", result.get("revision")
        )
        cls._add_field(lines, seen_values, "Title", result.get("title"))
        cls._add_field(
            lines,
            seen_values,
            "Sheet Number",
            result.get("sheet_number"),
        )
        cls._add_field(lines, seen_values, "Scale", result.get("scale"))
        cls._add_field(
            lines,
            seen_values,
            "Part Number",
            result.get("part_number"),
        )

        # Material / finish / units
        cls._add_field(
            lines, seen_values, "Material", result.get("material")
        )
        cls._add_field(lines, seen_values, "Finish", result.get("finish"))
        cls._add_field(lines, seen_values, "Units", result.get("units"))

        # Dimensions / tolerances / standards / components
        cls._add_field(
            lines,
            seen_values,
            "Part Numbers and Callouts",
            result.get("part_numbers"),
        )
        cls._add_field(
            lines,
            seen_values,
            "Referenced Parts",
            result.get("referenced_parts"),
        )
        cls._add_field(
            lines,
            seen_values,
            "Components",
            result.get("components"),
        )
        cls._add_field(
            lines,
            seen_values,
            "Dimensions",
            result.get("dimensions_text"),
        )
        cls._add_field(
            lines,
            seen_values,
            "Tolerances and GD&T",
            result.get("tolerances_text"),
        )
        cls._add_field(
            lines,
            seen_values,
            "Engineering Standards",
            result.get("engineering_standards"),
        )

        # Notes
        cls._add_field(
            lines,
            seen_values,
            "Manufacturing Process",
            result.get("manufacturing_process"),
        )
        cls._add_field(
            lines,
            seen_values,
            "Manufacturing and Inspection Notes",
            result.get("notes_text"),
        )
        cls._add_field(
            lines,
            seen_values,
            "Engineering Notes",
            result.get("engineering_notes"),
        )

        # Body
        cls._add_field(lines, seen_values, "Body", result.get("body"))

        score = (
            result.get("score")
            or result.get("bm25_score")
            or result.get("rank")
        )
        cls._add_field(lines, seen_values, "Retrieval Score", score)

        if result.get("exact_identifier_match"):
            cls._add_field(
                lines,
                seen_values,
                "Exact Identifier Match",
                "yes",
            )
            cls._add_field(
                lines,
                seen_values,
                "Matched Identifiers",
                result.get("matched_identifiers"),
            )

        searchable_text = cls._clean_value(
            result.get("searchable_text")
        )

        structured_field_count = len(lines)

        if searchable_text and structured_field_count <= 3:
            dedupe_key = searchable_text.casefold()

            if dedupe_key not in seen_values:
                lines.append(f"Extracted Content: {searchable_text}")

        return "\n".join(lines)

    @staticmethod
    def _order_results(
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        exact = [
            result
            for result in results
            if result.get("exact_identifier_match")
        ]
        other = [
            result
            for result in results
            if not result.get("exact_identifier_match")
        ]

        if not exact:
            return list(results)

        return exact + other

    @classmethod
    def build_context(
        cls,
        results: list[dict[str, Any]],
        max_documents: int = 5,
        max_characters: int = 16000,
    ) -> str:
        """
        Build structured context from ranked retrieval results.

        Args:
            results:
                Ranked search results. The highest-ranked result should
                appear first.
            max_documents:
                Maximum number of drawings to include.
            max_characters:
                Maximum total context length. Sections that would exceed
                this limit are omitted.

        Returns:
            A structured text block suitable for an LLM prompt.
        """
        if not results:
            return ""

        if max_documents <= 0:
            raise ValueError("max_documents must be greater than zero.")

        if max_characters <= 0:
            raise ValueError("max_characters must be greater than zero.")

        ordered_results = cls._order_results(results)
        sections: list[str] = []
        current_length = 0

        for position, result in enumerate(
            ordered_results[:max_documents],
            start=1,
        ):
            section = cls._build_document_section(
                result=result,
                position=position,
            )

            separator_length = 7 if sections else 0
            projected_length = (
                current_length
                + separator_length
                + len(section)
            )

            if projected_length > max_characters:
                if sections:
                    break

                truncated_section = cls._truncate_section(
                    section,
                    max_characters,
                )

                if truncated_section:
                    sections.append(truncated_section)

                break

            sections.append(section)
            current_length = projected_length

        return "\n\n---\n\n".join(sections)

    @staticmethod
    def _truncate_section(section: str, max_length: int) -> str:
        marker = "[context truncated]"

        if len(section) <= max_length:
            return section

        if max_length <= len(marker) + 1:
            return section[:max_length]

        budget = max_length - len(marker) - 1
        truncated = section[:budget]
        last_newline = truncated.rfind("\n")

        if last_newline > budget // 2:
            truncated = truncated[:last_newline]

        return truncated.rstrip() + "\n" + marker
