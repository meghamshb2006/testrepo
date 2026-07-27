from __future__ import annotations

import json
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
            f"- failure count: {summary.get('failures', 0)}",
            "",
            "## Retrieval Results",
            "",
            (
                "| Case | Category | Hit@1 | Hit@3 | Hit@5 | "
                "Reciprocal Rank | Retrieved Drawings | Latency | Error |"
            ),
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]

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
