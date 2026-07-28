"""
Deterministic retrieval confidence estimation.

Score in [0, 1] is a weighted blend of:
- top BM25 score relative to candidate scores (sigmoid of raw score)
- gap between top-1 and top-2 BM25 scores
- exact identifier match presence
- metadata field hits relevant to the query
- result/candidate count sanity
- non-empty context that is not only a truncation marker

Levels (defaults, overridable via app.config):
- HIGH   >= 0.80
- MEDIUM >= 0.50
- LOW    otherwise

confidence_explanation is a human-readable mapping of the same signals;
it does not change the score or level.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from search.services.query_preprocessor import PreprocessedQuery


@dataclass(frozen=True)
class ConfidenceResult:
    confidence_score: float
    confidence_level: str
    confidence_signals: dict[str, Any]
    confidence_explanation: list[str]


class RetrievalConfidenceEstimator:
    """Estimate lexical retrieval confidence from ranked results."""

    def __init__(
        self,
        high_threshold: float = 0.80,
        medium_threshold: float = 0.50,
        weight_top_score: float = 0.25,
        weight_score_gap: float = 0.20,
        weight_exact_match: float = 0.25,
        weight_metadata_hits: float = 0.15,
        weight_result_sanity: float = 0.10,
        weight_context: float = 0.05,
    ) -> None:
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
        self.weight_top_score = weight_top_score
        self.weight_score_gap = weight_score_gap
        self.weight_exact_match = weight_exact_match
        self.weight_metadata_hits = weight_metadata_hits
        self.weight_result_sanity = weight_result_sanity
        self.weight_context = weight_context

    @staticmethod
    def _sigmoid(value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))

    def _level_for(self, score: float) -> str:
        if score >= self.high_threshold:
            return "HIGH"

        if score >= self.medium_threshold:
            return "MEDIUM"

        return "LOW"

    @staticmethod
    def _build_explanation(signals: dict[str, Any]) -> list[str]:
        if signals.get("empty_results"):
            return ["No retrieval candidates"]

        explanation: list[str] = []

        if signals.get("exact_identifier_match"):
            matched = signals.get("matched_identifiers") or []
            if matched:
                explanation.append(
                    "Exact identifier match: " + ", ".join(str(m) for m in matched)
                )
            else:
                explanation.append("Exact identifier match")

        top_score_signal = float(signals.get("top_score_signal") or 0.0)
        if top_score_signal >= 0.85:
            explanation.append("High BM25 score")
        elif top_score_signal >= 0.60:
            explanation.append("Moderate BM25 score")
        else:
            explanation.append("Low BM25 score")

        score_gap_signal = float(signals.get("score_gap_signal") or 0.0)
        if score_gap_signal >= 0.70:
            explanation.append("Low ambiguity between top results")
        elif float(signals.get("second_bm25_score") or 0.0) > 0:
            explanation.append("Ambiguous top-result scores")

        metadata_checks = int(signals.get("metadata_checks") or 0)
        metadata_hits = int(signals.get("metadata_hits") or 0)
        if metadata_checks > 0 and metadata_hits > 0:
            explanation.append("Matched query-relevant metadata fields")
        elif metadata_checks > 0:
            explanation.append("Query metadata fields missing on top hit")

        context_signal = float(signals.get("context_signal") or 0.0)
        if context_signal >= 1.0:
            explanation.append("Non-empty retrieval context")
        elif context_signal > 0:
            explanation.append("Truncated retrieval context")
        else:
            explanation.append("Empty retrieval context")

        return explanation

    def estimate(
        self,
        results: list[dict[str, Any]],
        preprocessed: PreprocessedQuery,
        context: str,
        candidate_count: int,
    ) -> ConfidenceResult:
        if not results:
            signals = {
                "empty_results": True,
                "candidate_count": candidate_count,
            }
            return ConfidenceResult(
                confidence_score=0.0,
                confidence_level="LOW",
                confidence_signals=signals,
                confidence_explanation=self._build_explanation(signals),
            )

        top = results[0]
        top_score = float(top.get("bm25_score") or top.get("score") or 0.0)
        second_score = 0.0

        if len(results) > 1:
            second = results[1]
            second_score = float(
                second.get("bm25_score") or second.get("score") or 0.0
            )

        top_score_signal = self._sigmoid(top_score)
        score_gap = max(top_score - second_score, 0.0)
        score_gap_signal = self._sigmoid(score_gap)

        exact_match = bool(top.get("exact_identifier_match"))
        exact_match_signal = 1.0 if exact_match else 0.0

        metadata_hits = 0
        metadata_checks = 0
        identifier_types = {
            item.identifier_type for item in preprocessed.identifiers
        }

        field_checks = (
            ("drawing_number", "drawing_number"),
            ("revision", "revision"),
            ("material", "material"),
            ("standard", "engineering_standards"),
            ("part", "part_numbers"),
        )

        for identifier_type, field_name in field_checks:
            if identifier_type not in identifier_types:
                continue

            metadata_checks += 1
            value = top.get(field_name)

            if value is not None and str(value).strip():
                metadata_hits += 1

        metadata_signal = (
            metadata_hits / metadata_checks if metadata_checks else 0.5
        )

        result_count = len(results)
        sanity_signal = min(result_count / max(candidate_count, 1), 1.0)
        sanity_signal = max(sanity_signal, 0.2 if result_count > 0 else 0.0)

        context_text = (context or "").strip()
        context_signal = 0.0

        if context_text and context_text != "[context truncated]":
            context_signal = 1.0
        elif context_text:
            context_signal = 0.25

        score = (
            self.weight_top_score * top_score_signal
            + self.weight_score_gap * score_gap_signal
            + self.weight_exact_match * exact_match_signal
            + self.weight_metadata_hits * metadata_signal
            + self.weight_result_sanity * sanity_signal
            + self.weight_context * context_signal
        )
        score = max(0.0, min(1.0, round(score, 4)))

        signals = {
            "top_bm25_score": top_score,
            "second_bm25_score": second_score,
            "score_gap": score_gap,
            "top_score_signal": round(top_score_signal, 4),
            "score_gap_signal": round(score_gap_signal, 4),
            "exact_identifier_match": exact_match,
            "matched_identifiers": top.get("matched_identifiers", []),
            "metadata_hits": metadata_hits,
            "metadata_checks": metadata_checks,
            "metadata_signal": round(metadata_signal, 4),
            "result_count": result_count,
            "candidate_count": candidate_count,
            "sanity_signal": round(sanity_signal, 4),
            "context_signal": context_signal,
        }

        return ConfidenceResult(
            confidence_score=score,
            confidence_level=self._level_for(score),
            confidence_signals=signals,
            confidence_explanation=self._build_explanation(signals),
        )
