from __future__ import annotations

from search.diagnostics.retrieval_diagnostics import RetrievalDiagnostics


def test_explain_missing_expected_not_in_candidates() -> None:
    trace = {
        "original_query": "Find DR-9999",
        "normalized_query": "Find DR-9999",
        "candidate_drawing_ids": ["drawing-001"],
        "retrieved_documents": [
            {
                "drawing_id": "drawing-001",
                "drawing_number": "DR-1023",
                "rank": 1,
                "bm25_score": 1.2,
                "exact_identifier_match": False,
                "matched_terms": ["find"],
            }
        ],
        "score_breakdowns": [{"matched_fields": ["title"]}],
        "confidence_explanation": ["Moderate BM25 score"],
        "preprocessing_rules_applied": ["drawing_or_part_identifier_extraction"],
        "detected_identifiers": [{"value": "DR-9999", "type": "drawing_number"}],
        "candidate_count": 1,
        "result_count": 1,
        "latency_ms": 5.0,
    }

    explanation = RetrievalDiagnostics.explain_retrieval(
        trace,
        expected_ids=["drawing-002"],
    )

    assert explanation["why_retrieved"]
    assert explanation["why_not_retrieved"][0]["expected_id"] == "drawing-002"
    assert "FTS candidate" in explanation["why_not_retrieved"][0]["reason"]


def test_explain_missing_expected_in_candidates_but_not_topk() -> None:
    trace = {
        "candidate_drawing_ids": ["drawing-001", "drawing-002"],
        "retrieved_documents": [
            {
                "drawing_id": "drawing-001",
                "rank": 1,
                "bm25_score": 2.0,
                "matched_terms": ["aluminium"],
            }
        ],
        "score_breakdowns": [],
        "preprocessing_rules_applied": [],
        "detected_identifiers": [],
        "confidence_explanation": [],
    }

    explanation = RetrievalDiagnostics.explain_retrieval(
        trace,
        expected_ids=["drawing-002"],
    )

    assert "top-k" in explanation["why_not_retrieved"][0]["reason"]
