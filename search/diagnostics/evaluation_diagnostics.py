"""Per-case evaluation diagnostics built from retrieval traces."""

from __future__ import annotations

from typing import Any

from evaluation.metrics import normalise_identifier
from search.diagnostics.retrieval_diagnostics import RetrievalDiagnostics


class EvaluationDiagnostics:
    """Build compact diagnostics for evaluation cases."""

    @staticmethod
    def build_case_diagnostics(
        *,
        trace: dict[str, Any] | None,
        expected_identifiers: list[str],
        retrieved_identifiers: list[str],
        confidence_explanation: list[str] | None = None,
    ) -> dict[str, Any]:
        expected_normalised = {
            normalise_identifier(item)
            for item in expected_identifiers
            if item and str(item).strip()
        }
        retrieved_normalised = {
            normalise_identifier(item)
            for item in retrieved_identifiers
            if item and str(item).strip()
        }

        false_positives = sorted(
            retrieved_normalised - expected_normalised
        ) if expected_normalised else sorted(retrieved_normalised)
        false_negatives = sorted(
            expected_normalised - retrieved_normalised
        )

        explanation = RetrievalDiagnostics.explain_retrieval(
            trace or {},
            expected_ids=expected_identifiers,
        )

        if confidence_explanation:
            explanation["confidence_explanation"] = list(
                confidence_explanation
            )

        return {
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "preprocessing_rules_applied": explanation.get(
                "preprocessing_rules_applied"
            )
            or [],
            "confidence_explanation": explanation.get(
                "confidence_explanation"
            )
            or [],
            "why_retrieved": explanation.get("why_retrieved") or [],
            "why_not_retrieved": explanation.get("why_not_retrieved") or [],
            "matched_fields_top_hit": explanation.get(
                "matched_fields_top_hit"
            )
            or [],
            "detected_identifiers": explanation.get("detected_identifiers")
            or [],
        }
