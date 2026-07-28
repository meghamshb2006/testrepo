from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any


class EvaluationReportBuilder:
    """Formats evaluation results as JSON or Markdown."""

    @classmethod
    def to_json(
        cls,
        evaluation: dict[str, Any],
        indent: int = 2,
    ) -> str:
        return json.dumps(evaluation, indent=indent, default=str)

    @classmethod
    def to_markdown(cls, evaluation: dict[str, Any]) -> str:
        dataset = evaluation.get("dataset") or {}
        summary = evaluation.get("summary") or {}
        retrieval_results = evaluation.get("retrieval_results") or []
        answer_results = evaluation.get("answer_results") or []

        lines: list[str] = [
            "# Engineering Drawing Evaluation Report",
            "",
            "## Dataset",
            f"- name: {dataset.get('name', '')}",
            f"- version: {dataset.get('version', '')}",
            f"- case count: {summary.get('total_cases', 0)}",
            "",
            "## Summary",
            f"- Hit@1: {cls._format_percentage(summary.get('hit_at_1', 0.0))}",
            f"- Hit@3: {cls._format_percentage(summary.get('hit_at_3', 0.0))}",
            f"- Hit@5: {cls._format_percentage(summary.get('hit_at_5', 0.0))}",
            f"- MRR: {cls._format_float(summary.get('mean_reciprocal_rank', 0.0))}",
            (
                "- answer term recall: "
                f"{cls._format_percentage(summary.get('answer_term_recall', 0.0))}"
            ),
            (
                "- source accuracy: "
                f"{cls._format_percentage(summary.get('source_accuracy', 0.0))}"
            ),
            (
                "- refusal accuracy: "
                f"{cls._format_percentage(summary.get('refusal_accuracy', 0.0))}"
            ),
            (
                "- grounded response rate: "
                f"{cls._format_percentage(summary.get('grounded_response_rate', 0.0))}"
            ),
            (
                "- mean retrieval latency: "
                f"{cls._format_latency(summary.get('retrieval_latency_mean_ms', 0.0))}"
            ),
            (
                "- p95 retrieval latency: "
                f"{cls._format_latency(summary.get('retrieval_latency_p95_ms', 0.0))}"
            ),
            (
                "- mean answer latency: "
                f"{cls._format_latency(summary.get('answer_latency_mean_ms', 0.0))}"
            ),
            (
                "- p95 answer latency: "
                f"{cls._format_latency(summary.get('answer_latency_p95_ms', 0.0))}"
            ),
            (
                "- mean context length: "
                f"{cls._format_float(summary.get('mean_context_length', 0.0))}"
            ),
            (
                "- confidence HIGH rate: "
                f"{cls._format_percentage(summary.get('confidence_high_rate', 0.0))}"
            ),
            (
                "- confidence MEDIUM rate: "
                f"{cls._format_percentage(summary.get('confidence_medium_rate', 0.0))}"
            ),
            (
                "- confidence LOW rate: "
                f"{cls._format_percentage(summary.get('confidence_low_rate', 0.0))}"
            ),
            (
                "- confidence accuracy: "
                + (
                    cls._format_percentage(summary["confidence_accuracy"])
                    if summary.get("confidence_accuracy") is not None
                    else "n/a"
                )
            ),
            (
                "- false positive rate: "
                f"{cls._format_percentage(summary.get('false_positive_rate', 0.0))}"
            ),
            (
                "- false negative rate: "
                f"{cls._format_percentage(summary.get('false_negative_rate', 0.0))}"
            ),
            (
                "- exact identifier match rate: "
                f"{cls._format_percentage(summary.get('exact_identifier_match_rate', 0.0))}"
            ),
            (
                "- mean retrieved documents: "
                f"{cls._format_float(summary.get('mean_retrieved_documents', 0.0))}"
            ),
            (
                "- confidence calibration: "
                + (
                    cls._format_percentage(summary["confidence_calibration"])
                    if summary.get("confidence_calibration") is not None
                    else "n/a"
                )
            ),
            f"- failure count: {summary.get('failures', 0)}",
            "",
            "## Category Breakdown",
            "",
        ]

        category_metrics = summary.get("category_metrics") or {}
        if category_metrics:
            lines.extend(
                [
                    (
                        "| Category | Cases | Hit@1 | Hit@5 | MRR | "
                        "Mean Latency | Mean Context |"
                    ),
                    "| --- | --- | --- | --- | --- | --- | --- |",
                ]
            )
            for category, metrics in category_metrics.items():
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            cls._escape_cell(category),
                            cls._escape_cell(int(metrics.get("case_count", 0))),
                            cls._format_percentage(metrics.get("hit_at_1", 0.0)),
                            cls._format_percentage(metrics.get("hit_at_5", 0.0)),
                            cls._format_float(
                                metrics.get("mean_reciprocal_rank", 0.0)
                            ),
                            cls._format_latency(
                                metrics.get("mean_latency_ms", 0.0)
                            ),
                            cls._format_float(
                                metrics.get("mean_context_length", 0.0)
                            ),
                        ]
                    )
                    + " |"
                )
        else:
            lines.append("- No category metadata available.")

        regression = evaluation.get("regression")
        if regression:
            lines.extend(["", "## Regression vs Baseline", ""])
            lines.append(f"- ok: {regression.get('ok')}")
            lines.append(
                f"- regression count: {regression.get('regression_count', 0)}"
            )
            for item in regression.get("comparisons") or []:
                lines.append(
                    f"- {item.get('metric')}: "
                    f"{cls._format_float(item.get('baseline', 0.0))} -> "
                    f"{cls._format_float(item.get('current', 0.0))} "
                    f"(delta={float(item.get('delta', 0.0)):+.3f})"
                )

        lines.extend(
            [
                "",
                "## Retrieval Results",
                "",
                (
                    "| Case | Category | Hit@1 | Hit@3 | Hit@5 | "
                    "Reciprocal Rank | Confidence | Context Len | "
                    "Retrieved Drawings | Latency | Error |"
                ),
                (
                    "| --- | --- | --- | --- | --- | --- | --- | --- | "
                    "--- | --- | --- |"
                ),
            ]
        )

        for result in retrieval_results:
            retrieved = ", ".join(result.get("retrieved_identifiers") or [])
            lines.append(
                "| "
                + " | ".join(
                    [
                        cls._escape_cell(result.get("case_id", "")),
                        cls._escape_cell(result.get("category") or ""),
                        cls._format_bool(result.get("hit_at_1")),
                        cls._format_bool(result.get("hit_at_3")),
                        cls._format_bool(result.get("hit_at_5")),
                        cls._format_float(result.get("reciprocal_rank", 0.0)),
                        cls._escape_cell(result.get("confidence_level") or ""),
                        cls._escape_cell(result.get("context_length", 0)),
                        cls._escape_cell(retrieved),
                        cls._format_latency(result.get("latency_ms", 0.0)),
                        cls._escape_cell(result.get("error") or ""),
                    ]
                )
                + " |"
            )

        lines.extend(
            [
                "",
                "## Answer Results",
                "",
                (
                    "| Case | Answerable | Grounded | Expected Terms Found | "
                    "Missing Terms | Forbidden Terms | Source Match | "
                    "Refusal Correct | Latency | Error |"
                ),
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )

        for result in answer_results:
            lines.append(
                "| "
                + " | ".join(
                    [
                        cls._escape_cell(result.get("case_id", "")),
                        cls._format_bool(result.get("answerable")),
                        cls._format_bool(result.get("grounded")),
                        cls._escape_cell(
                            ", ".join(result.get("expected_terms_found") or [])
                        ),
                        cls._escape_cell(
                            ", ".join(
                                result.get("expected_terms_missing") or []
                            )
                        ),
                        cls._escape_cell(
                            ", ".join(
                                result.get("forbidden_terms_found") or []
                            )
                        ),
                        cls._format_bool(result.get("source_match")),
                        cls._format_optional_bool(
                            result.get("refusal_correct")
                        ),
                        cls._format_latency(result.get("latency_ms", 0.0)),
                        cls._escape_cell(result.get("error") or ""),
                    ]
                )
                + " |"
            )

        lines.extend(
            [
                "",
                "## Diagnostics Excerpt",
                "",
            ]
        )

        diagnostics_added = False

        for result in retrieval_results[:10]:
            diagnostics = result.get("diagnostics") or {}
            if not diagnostics:
                continue

            diagnostics_added = True
            false_negatives = ", ".join(
                diagnostics.get("false_negatives") or []
            ) or "none"
            explanation = "; ".join(
                diagnostics.get("confidence_explanation") or []
            ) or "n/a"
            lines.append(
                f"- `{result.get('case_id')}`: FN={false_negatives}; "
                f"confidence={explanation}"
            )

        if not diagnostics_added:
            lines.append("- No diagnostics available.")

        failure_lines: list[str] = []

        for result in retrieval_results:
            if result.get("error"):
                failure_lines.append(
                    f"- retrieval `{result.get('case_id')}`: "
                    f"{result.get('error')}"
                )

        for result in answer_results:
            if result.get("error"):
                failure_lines.append(
                    f"- answer `{result.get('case_id')}`: "
                    f"{result.get('error')}"
                )

        lines.extend(
            [
                "",
                "## Failures and Observations",
                "",
            ]
        )

        if failure_lines:
            lines.extend(failure_lines)
        else:
            lines.append("- No case-level evaluation errors.")

        lines.append("")

        return "\n".join(lines)

    @classmethod
    def to_csv(cls, evaluation: dict[str, Any]) -> str:
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "case_id",
                "category",
                "question",
                "hit_at_1",
                "hit_at_3",
                "hit_at_5",
                "reciprocal_rank",
                "confidence_level",
                "confidence_score",
                "exact_identifier_match",
                "result_count",
                "candidate_count",
                "context_length",
                "latency_ms",
                "retrieved_identifiers",
                "error",
            ]
        )

        for result in evaluation.get("retrieval_results") or []:
            writer.writerow(
                [
                    result.get("case_id", ""),
                    result.get("category") or "",
                    result.get("question", ""),
                    result.get("hit_at_1"),
                    result.get("hit_at_3"),
                    result.get("hit_at_5"),
                    result.get("reciprocal_rank", 0.0),
                    result.get("confidence_level") or "",
                    result.get("confidence_score"),
                    result.get("exact_identifier_match"),
                    result.get("result_count", 0),
                    result.get("candidate_count", 0),
                    result.get("context_length", 0),
                    result.get("latency_ms", 0.0),
                    ";".join(result.get("retrieved_identifiers") or []),
                    result.get("error") or "",
                ]
            )

        return buffer.getvalue()

    @staticmethod
    def _escape_cell(value: Any) -> str:
        text = str(value).replace("\n", " ").replace("|", "\\|")
        return text

    @staticmethod
    def _format_percentage(value: Any) -> str:
        return f"{float(value) * 100.0:.1f}%"

    @staticmethod
    def _format_float(value: Any) -> str:
        return f"{float(value):.2f}"

    @staticmethod
    def _format_latency(value: Any) -> str:
        return f"{float(value):.1f} ms"

    @staticmethod
    def _format_bool(value: Any) -> str:
        return "true" if bool(value) else "false"

    @staticmethod
    def _format_optional_bool(value: Any) -> str:
        if value is None:
            return ""

        return "true" if bool(value) else "false"
