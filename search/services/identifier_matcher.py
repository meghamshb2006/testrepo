"""Exact engineering-identifier boost over BM25-ranked results."""

from __future__ import annotations

import re
from typing import Any

from search.services.query_preprocessor import IdentifierMatch


class ExactIdentifierBooster:
    """Promote results that exactly match detected query identifiers."""

    _MATCH_FIELDS = (
        "drawing_number",
        "part_number",
        "part_numbers",
        "material",
        "revision",
        "tolerances_text",
        "engineering_standards",
        "components",
        "referenced_parts",
    )

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()

    @classmethod
    def _field_tokens(cls, value: Any) -> list[str]:
        if value is None:
            return []

        text = str(value)
        tokens = re.split(r"[\s,/|;]+", text)
        return [cls._normalize(token) for token in tokens if token.strip()]

    @classmethod
    def _document_matches(
        cls,
        result: dict[str, Any],
        identifier: IdentifierMatch,
    ) -> bool:
        target = cls._normalize(identifier.value)
        revision_code = None

        if identifier.identifier_type == "revision":
            revision_code = cls._normalize(
                identifier.value.replace("REV", "").strip()
            )

        for field_name in cls._MATCH_FIELDS:
            field_value = result.get(field_name)

            if field_value is None:
                continue

            normalized_field = cls._normalize(str(field_value))

            if target and target in normalized_field:
                return True

            if revision_code and field_name == "revision":
                if normalized_field == revision_code:
                    return True

            for token in cls._field_tokens(field_value):
                if token == target:
                    return True

                if revision_code and token == revision_code:
                    return True

                if (
                    identifier.identifier_type == "material"
                    and target in token
                ):
                    return True

        return False

    def boost(
        self,
        results: list[dict[str, Any]],
        identifiers: list[IdentifierMatch],
    ) -> list[dict[str, Any]]:
        if not results:
            return []

        annotated: list[dict[str, Any]] = []

        for result in results:
            matched = [
                identifier.value
                for identifier in identifiers
                if self._document_matches(result, identifier)
            ]
            updated = dict(result)
            updated["exact_identifier_match"] = bool(matched)
            updated["matched_identifiers"] = matched
            annotated.append(updated)

        if not identifiers:
            return annotated

        matches = [
            result
            for result in annotated
            if result["exact_identifier_match"]
        ]
        non_matches = [
            result
            for result in annotated
            if not result["exact_identifier_match"]
        ]

        reordered = matches + non_matches

        for index, result in enumerate(reordered, start=1):
            result["rank"] = index

        return reordered
