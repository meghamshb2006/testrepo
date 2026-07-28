"""Explanatory retrieval score breakdowns (annotation only; no ranking change)."""

from __future__ import annotations

import re
from typing import Any

from search.services.query_preprocessor import IdentifierMatch


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


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _field_tokens(value: Any) -> list[str]:
    if value is None:
        return []

    text = str(value)
    tokens = re.split(r"[\s,/|;]+", text)
    return [_normalize(token) for token in tokens if token.strip()]


def matched_fields_for_result(
    result: dict[str, Any],
    identifiers: list[IdentifierMatch],
) -> list[str]:
    """Return document field names that matched any query identifier."""
    matched: list[str] = []
    seen: set[str] = set()

    for identifier in identifiers:
        target = _normalize(identifier.value)
        revision_code = None

        if identifier.identifier_type == "revision":
            revision_code = _normalize(
                identifier.value.replace("REV", "").strip()
            )

        for field_name in _MATCH_FIELDS:
            field_value = result.get(field_name)

            if field_value is None:
                continue

            normalized_field = _normalize(str(field_value))
            hit = False

            if target and target in normalized_field:
                hit = True
            elif revision_code and field_name == "revision":
                if normalized_field == revision_code:
                    hit = True
            else:
                for token in _field_tokens(field_value):
                    if token == target or (
                        revision_code and token == revision_code
                    ):
                        hit = True
                        break

                    if (
                        identifier.identifier_type == "material"
                        and target in token
                    ):
                        hit = True
                        break

            if hit and field_name not in seen:
                seen.add(field_name)
                matched.append(field_name)

    return matched


def build_score_breakdown(
    result: dict[str, Any],
    identifiers: list[IdentifierMatch] | None = None,
) -> dict[str, Any]:
    """
    Build an explanatory score breakdown for a retrieved document.

    Does not alter ranking. final_score always equals base_bm25_score.
    Bonus fields are annotations only (0.0 display placeholders).
    """
    identifiers = identifiers or []
    base_score = float(result.get("bm25_score") or result.get("score") or 0.0)
    exact_match = bool(result.get("exact_identifier_match"))
    matched_identifiers = list(result.get("matched_identifiers") or [])
    matched_tokens = list(result.get("matched_terms") or [])
    matched_fields = matched_fields_for_result(result, identifiers)

    return {
        "drawing_id": result.get("drawing_id"),
        "base_bm25_score": base_score,
        "exact_identifier_bonus": 0.0,
        "metadata_match_bonus": 0.0,
        "final_score": base_score,
        "exact_identifier_match": exact_match,
        "matched_fields": matched_fields,
        "matched_tokens": matched_tokens,
        "matched_identifiers": matched_identifiers,
    }


def build_score_breakdowns(
    results: list[dict[str, Any]],
    identifiers: list[IdentifierMatch] | None = None,
) -> list[dict[str, Any]]:
    return [
        build_score_breakdown(result, identifiers)
        for result in results
    ]
