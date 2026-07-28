"""Build RetrievalTrace objects from retrieval pipeline intermediates."""

from __future__ import annotations

from typing import Any

from search.models.retrieval_trace import (
    RetrievedDocumentTrace,
    RetrievalTrace,
)
from search.services.query_preprocessor import PreprocessedQuery
from search.services.score_breakdown import build_score_breakdowns


class RetrievalTraceBuilder:
    """Assembles a serializable retrieval trace for developer diagnostics."""

    @staticmethod
    def _preprocessing_rules(
        preprocessed: PreprocessedQuery,
    ) -> list[str]:
        rules: list[str] = []
        types = {item.identifier_type for item in preprocessed.identifiers}

        if "revision" in types:
            rules.append("revision_normalization")
        if "material" in types:
            rules.append("material_hyphen_normalization")
        if "standard" in types:
            rules.append("standard_normalization")
        if "thread" in types:
            rules.append("thread_normalization")
        if "drawing_number" in types or "part" in types:
            rules.append("drawing_or_part_identifier_extraction")
        if "dimension" in types:
            rules.append("dimension_extraction")
        if preprocessed.residual_tokens:
            rules.append("residual_token_retention")

        return rules

    @classmethod
    def build(
        cls,
        *,
        original_query: str,
        preprocessed: PreprocessedQuery,
        fts_query: str,
        query_tokens: list[str],
        candidates: list[dict[str, Any]],
        results: list[dict[str, Any]],
        confidence_score: float,
        confidence_level: str,
        confidence_explanation: list[str],
        stage_latencies_ms: dict[str, float],
        latency_ms: float,
        error: str | None = None,
    ) -> RetrievalTrace:
        retrieved = [
            RetrievedDocumentTrace(
                drawing_id=result.get("drawing_id"),
                drawing_number=result.get("drawing_number"),
                rank=result.get("rank"),
                bm25_score=(
                    float(result["bm25_score"])
                    if result.get("bm25_score") is not None
                    else None
                ),
                exact_identifier_match=bool(
                    result.get("exact_identifier_match")
                ),
                matched_identifiers=list(
                    result.get("matched_identifiers") or []
                ),
                matched_terms=list(result.get("matched_terms") or []),
            )
            for result in results
        ]

        bm25_scores = [
            float(result.get("bm25_score") or 0.0) for result in results
        ]

        candidate_ids = [
            str(candidate.get("drawing_id"))
            for candidate in candidates
            if candidate.get("drawing_id") is not None
        ]

        return RetrievalTrace(
            original_query=original_query,
            normalized_query=preprocessed.normalized_query,
            fts_query=fts_query,
            query_tokens=query_tokens,
            residual_tokens=list(preprocessed.residual_tokens),
            detected_identifiers=[
                {
                    "value": item.value,
                    "type": item.identifier_type,
                    "raw": item.raw,
                }
                for item in preprocessed.identifiers
            ],
            candidate_count=len(candidates),
            result_count=len(results),
            retrieved_documents=retrieved,
            bm25_scores=bm25_scores,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            confidence_explanation=list(confidence_explanation),
            score_breakdowns=build_score_breakdowns(
                results,
                preprocessed.identifiers,
            ),
            latency_ms=round(latency_ms, 3),
            stage_latencies_ms={
                key: round(value, 3)
                for key, value in stage_latencies_ms.items()
            },
            candidate_drawing_ids=candidate_ids,
            preprocessing_rules_applied=cls._preprocessing_rules(
                preprocessed
            ),
            error=error,
        )
