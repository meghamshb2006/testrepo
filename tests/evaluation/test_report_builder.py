from __future__ import annotations

import json

from evaluation.reporting.report_builder import EvaluationReportBuilder


def _sample_evaluation() -> dict:
    return {
        "dataset": {"name": "demo", "version": "1.0"},
        "retrieval_results": [
            {
                "case_id": "case|a",
                "category": "material",
                "hit_at_1": True,
                "hit_at_3": True,
                "hit_at_5": True,
                "reciprocal_rank": 1.0,
                "retrieved_identifiers": ["drawing-001"],
                "latency_ms": 12.34,
                "error": None,
            }
        ],
        "answer_results": [
            {
                "case_id": "case|a",
                "answerable": True,
                "grounded": True,
                "expected_terms_found": ["6061-T6"],
                "expected_terms_missing": [],
                "forbidden_terms_found": [],
                "source_match": True,
                "refusal_correct": None,
                "latency_ms": 20.0,
                "error": None,
                "answer": "Aluminium 6061-T6",
            }
        ],
        "summary": {
            "total_cases": 1,
            "hit_at_1": 1.0,
            "hit_at_3": 1.0,
            "hit_at_5": 1.0,
            "mean_reciprocal_rank": 1.0,
            "answer_term_recall": 1.0,
            "source_accuracy": 1.0,
            "refusal_accuracy": 0.0,
            "grounded_response_rate": 1.0,
            "retrieval_latency_mean_ms": 12.34,
            "retrieval_latency_p95_ms": 12.34,
            "answer_latency_mean_ms": 20.0,
            "answer_latency_p95_ms": 20.0,
            "failures": 0,
        },
    }


def test_valid_json_output() -> None:
    text = EvaluationReportBuilder.to_json(_sample_evaluation())
    payload = json.loads(text)

    assert payload["dataset"]["name"] == "demo"
    assert "context" not in text
    assert "prompt" not in text.lower() or "prompt" not in payload


def test_markdown_summary_and_pipe_escaping() -> None:
    markdown = EvaluationReportBuilder.to_markdown(_sample_evaluation())

    assert "# Engineering Drawing Evaluation Report" in markdown
    assert "Hit@1: 100.0%" in markdown
    assert "case\\|a" in markdown
    assert "12.3 ms" in markdown
    assert "context" not in markdown.lower() or "ContextBuilder" not in markdown
    assert "SYSTEM INSTRUCTIONS" not in markdown
