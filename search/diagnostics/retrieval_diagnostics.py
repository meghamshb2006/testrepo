"""Retrieval diagnostics for explaining matches and misses."""

from __future__ import annotations

from typing import Any


class RetrievalDiagnostics:
    """Explain why documents were retrieved or missed."""

    @staticmethod
    def explain_retrieval(
        trace: dict[str, Any],
        expected_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        expected = [
            item.strip()
            for item in (expected_ids or [])
            if item and str(item).strip()
        ]
        retrieved_docs = trace.get("retrieved_documents") or []
        candidate_ids = {
            str(item).casefold()
            for item in (trace.get("candidate_drawing_ids") or [])
        }
        retrieved_ids = {
            str(doc.get("drawing_id")).casefold()
            for doc in retrieved_docs
            if doc.get("drawing_id") is not None
        }

        why_retrieved: list[dict[str, Any]] = []

        for doc in retrieved_docs:
            drawing_id = doc.get("drawing_id")
            reasons: list[str] = []

            if doc.get("exact_identifier_match"):
                matched = doc.get("matched_identifiers") or []
                reasons.append(
                    "Exact identifier match: "
                    + (", ".join(matched) if matched else "yes")
                )

            matched_terms = doc.get("matched_terms") or []
            if matched_terms:
                reasons.append(
                    "Matched tokens: " + ", ".join(matched_terms)
                )

            if doc.get("bm25_score") is not None:
                reasons.append(f"BM25 score: {doc.get('bm25_score')}")

            why_retrieved.append(
                {
                    "drawing_id": drawing_id,
                    "drawing_number": doc.get("drawing_number"),
                    "rank": doc.get("rank"),
                    "reasons": reasons,
                }
            )

        why_not_retrieved: list[dict[str, Any]] = []

        for expected_id in expected:
            key = expected_id.casefold()

            if key in retrieved_ids:
                continue

            if key not in candidate_ids:
                reason = (
                    "Not present in FTS candidate set for this query"
                )
            else:
                reason = (
                    "Present in FTS candidates but not ranked into top-k "
                    "BM25 results (or filtered by matched_terms)"
                )

            why_not_retrieved.append(
                {
                    "expected_id": expected_id,
                    "reason": reason,
                }
            )

        score_breakdowns = trace.get("score_breakdowns") or []
        matched_fields: list[str] = []

        if score_breakdowns:
            matched_fields = list(
                score_breakdowns[0].get("matched_fields") or []
            )

        return {
            "original_query": trace.get("original_query"),
            "normalized_query": trace.get("normalized_query"),
            "preprocessing_rules_applied": trace.get(
                "preprocessing_rules_applied"
            )
            or [],
            "detected_identifiers": trace.get("detected_identifiers") or [],
            "confidence_level": trace.get("confidence_level"),
            "confidence_explanation": trace.get("confidence_explanation")
            or [],
            "matched_fields_top_hit": matched_fields,
            "why_retrieved": why_retrieved,
            "why_not_retrieved": why_not_retrieved,
            "candidate_count": trace.get("candidate_count", 0),
            "result_count": trace.get("result_count", 0),
            "latency_ms": trace.get("latency_ms", 0.0),
        }
