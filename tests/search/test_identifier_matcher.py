from __future__ import annotations

from search.services.identifier_matcher import ExactIdentifierBooster
from search.services.query_preprocessor import IdentifierMatch


def test_exact_drawing_number_beats_higher_bm25_non_match() -> None:
    booster = ExactIdentifierBooster()
    results = [
        {
            "rank": 1,
            "drawing_id": "drawing-002",
            "drawing_number": "DR-2048",
            "bm25_score": 9.0,
            "material": "Steel",
        },
        {
            "rank": 2,
            "drawing_id": "drawing-001",
            "drawing_number": "DR-1023",
            "bm25_score": 2.0,
            "material": "Aluminium 6061-T6",
        },
    ]
    identifiers = [
        IdentifierMatch(
            value="DR-1023",
            identifier_type="drawing_number",
            raw="DR-1023",
        )
    ]

    boosted = booster.boost(results, identifiers)

    assert boosted[0]["drawing_id"] == "drawing-001"
    assert boosted[0]["exact_identifier_match"] is True
    assert boosted[0]["matched_identifiers"] == ["DR-1023"]
    assert boosted[0]["rank"] == 1
    assert boosted[1]["drawing_id"] == "drawing-002"
    assert boosted[1]["exact_identifier_match"] is False


def test_boost_preserves_relative_order_within_groups() -> None:
    booster = ExactIdentifierBooster()
    results = [
        {
            "rank": 1,
            "drawing_id": "a",
            "drawing_number": "DR-1",
            "bm25_score": 5.0,
        },
        {
            "rank": 2,
            "drawing_id": "b",
            "drawing_number": "DR-2",
            "bm25_score": 4.0,
        },
        {
            "rank": 3,
            "drawing_id": "c",
            "drawing_number": "DR-1",
            "bm25_score": 3.0,
        },
    ]
    identifiers = [
        IdentifierMatch(
            value="DR-1",
            identifier_type="drawing_number",
            raw="DR-1",
        )
    ]

    boosted = booster.boost(results, identifiers)

    assert [item["drawing_id"] for item in boosted] == ["a", "c", "b"]
