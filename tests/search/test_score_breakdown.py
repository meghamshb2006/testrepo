from __future__ import annotations

from search.services.query_preprocessor import IdentifierMatch
from search.services.score_breakdown import build_score_breakdown


def test_score_breakdown_is_annotation_only() -> None:
    result = {
        "drawing_id": "drawing-001",
        "drawing_number": "DR-1023",
        "bm25_score": 2.5,
        "exact_identifier_match": True,
        "matched_identifiers": ["DR-1023"],
        "matched_terms": ["dr", "1023"],
    }
    identifiers = [
        IdentifierMatch(
            value="DR-1023",
            identifier_type="drawing_number",
            raw="DR-1023",
        )
    ]

    breakdown = build_score_breakdown(result, identifiers)

    assert breakdown["base_bm25_score"] == 2.5
    assert breakdown["final_score"] == 2.5
    assert breakdown["exact_identifier_bonus"] == 0.0
    assert breakdown["metadata_match_bonus"] == 0.0
    assert "drawing_number" in breakdown["matched_fields"]
