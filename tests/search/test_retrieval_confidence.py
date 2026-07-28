from __future__ import annotations

from search.services.query_preprocessor import (
    EngineeringQueryPreprocessor,
    PreprocessedQuery,
)
from search.services.retrieval_confidence import RetrievalConfidenceEstimator


def _preprocessed(query: str = "DR-1023") -> PreprocessedQuery:
    return EngineeringQueryPreprocessor().preprocess(query)


def test_empty_results_are_low_confidence() -> None:
    estimator = RetrievalConfidenceEstimator()
    result = estimator.estimate(
        results=[],
        preprocessed=_preprocessed(),
        context="",
        candidate_count=0,
    )

    assert result.confidence_score == 0.0
    assert result.confidence_level == "LOW"
    assert "No retrieval candidates" in result.confidence_explanation


def test_exact_match_tends_high() -> None:
    estimator = RetrievalConfidenceEstimator()
    result = estimator.estimate(
        results=[
            {
                "bm25_score": 4.5,
                "exact_identifier_match": True,
                "matched_identifiers": ["DR-1023"],
                "drawing_number": "DR-1023",
                "revision": "C",
                "material": "Aluminium 6061-T6",
            },
            {"bm25_score": 0.4},
        ],
        preprocessed=_preprocessed("Find drawing DR-1023"),
        context="Retrieved Drawing 1\nDrawing Number: DR-1023",
        candidate_count=5,
    )

    assert result.confidence_score >= 0.80
    assert result.confidence_level == "HIGH"
    assert any(
        "Exact identifier match" in item
        for item in result.confidence_explanation
    )


def test_ambiguous_gap_is_not_high() -> None:
    estimator = RetrievalConfidenceEstimator()
    result = estimator.estimate(
        results=[
            {
                "bm25_score": 1.1,
                "exact_identifier_match": False,
                "matched_identifiers": [],
            },
            {"bm25_score": 1.05},
        ],
        preprocessed=_preprocessed("aluminium bracket"),
        context="Retrieved Drawing 1\nTitle: Bracket",
        candidate_count=20,
    )

    assert result.confidence_level in {"LOW", "MEDIUM"}
    assert result.confidence_score < 0.80
    assert result.confidence_explanation
