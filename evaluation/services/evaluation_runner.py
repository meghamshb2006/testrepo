from __future__ import annotations

from typing import Any

from evaluation.evaluators.answer_evaluator import AnswerEvaluator
from evaluation.evaluators.retrieval_evaluator import RetrievalEvaluator
from evaluation.metrics import mean, percentile
from evaluation.schemas import (
    AnswerEvaluationResult,
    BenchmarkDataset,
    EvaluationSummary,
    RetrievalEvaluationResult,
)


class EvaluationRunner:
    """Runs retrieval and optional answer evaluation over a benchmark dataset."""

    def __init__(
        self,
        retrieval_evaluator: RetrievalEvaluator,
        answer_evaluator: AnswerEvaluator | None = None,
    ) -> None:
        self.retrieval_evaluator = retrieval_evaluator
        self.answer_evaluator = answer_evaluator

    def run(
        self,
        dataset: BenchmarkDataset,
        evaluate_answers: bool = False,
        default_candidate_limit: int = 30,
        default_top_k: int = 5,
        default_max_context_characters: int = 16000,
    ) -> dict[str, Any]:
        if evaluate_answers and self.answer_evaluator is None:
            raise ValueError(
                "answer_evaluator is required when evaluate_answers=True."
            )

        retrieval_results: list[RetrievalEvaluationResult] = []
        answer_results: list[AnswerEvaluationResult] = []
        failures = 0

        for case in dataset.cases:
            retrieval_result = self.retrieval_evaluator.evaluate_case(
                case=case,
                default_candidate_limit=default_candidate_limit,
                default_top_k=default_top_k,
                default_max_context_characters=default_max_context_characters,
            )
            retrieval_results.append(retrieval_result)

            if retrieval_result.error:
                failures += 1

            if not evaluate_answers:
                continue

            assert self.answer_evaluator is not None

            answer_result = self.answer_evaluator.evaluate_case(
                case=case,
                default_candidate_limit=default_candidate_limit,
                default_top_k=default_top_k,
                default_max_context_characters=default_max_context_characters,
            )
            answer_results.append(answer_result)

            if answer_result.error:
                failures += 1

        summary = self._build_summary(
            dataset=dataset,
            retrieval_results=retrieval_results,
            answer_results=answer_results,
            failures=failures,
        )

        return {
            "dataset": {
                "name": dataset.name,
                "version": dataset.version,
            },
            "retrieval_results": [
                result.model_dump(mode="json")
                for result in retrieval_results
            ],
            "answer_results": [
                result.model_dump(mode="json")
                for result in answer_results
            ],
            "summary": summary.model_dump(mode="json"),
        }

    @staticmethod
    def _build_summary(
        dataset: BenchmarkDataset,
        retrieval_results: list[RetrievalEvaluationResult],
        answer_results: list[AnswerEvaluationResult],
        failures: int,
    ) -> EvaluationSummary:
        retrieval_count = len(retrieval_results)
        answer_count = len(answer_results)

        hit_at_1 = mean(
            [1.0 if result.hit_at_1 else 0.0 for result in retrieval_results]
        )
        hit_at_3 = mean(
            [1.0 if result.hit_at_3 else 0.0 for result in retrieval_results]
        )
        hit_at_5 = mean(
            [1.0 if result.hit_at_5 else 0.0 for result in retrieval_results]
        )
        mean_rr = mean(
            [result.reciprocal_rank for result in retrieval_results]
        )
        retrieval_latencies = [
            result.latency_ms for result in retrieval_results
        ]
        context_lengths = [
            float(result.context_length) for result in retrieval_results
        ]
        confidence_levels = [
            (result.confidence_level or "").upper()
            for result in retrieval_results
            if result.confidence_level
        ]
        confidence_matches = [
            1.0 if result.confidence_level_match else 0.0
            for result in retrieval_results
            if result.confidence_level_match is not None
        ]

        term_recalls: list[float] = []
        source_scores: list[float] = []
        refusal_scores: list[float] = []
        grounded_scores: list[float] = []
        answer_latencies: list[float] = []

        for result in answer_results:
            answer_latencies.append(result.latency_ms)
            grounded_scores.append(1.0 if result.grounded else 0.0)

            total_terms = (
                len(result.expected_terms_found)
                + len(result.expected_terms_missing)
            )

            if total_terms == 0:
                term_recalls.append(1.0)
            else:
                term_recalls.append(
                    len(result.expected_terms_found) / float(total_terms)
                )

            if result.answerable:
                source_scores.append(1.0 if result.source_match else 0.0)
            else:
                refusal_scores.append(
                    1.0 if result.refusal_correct else 0.0
                )

        confidence_accuracy = (
            mean(confidence_matches) if confidence_matches else None
        )

        false_positive_scores: list[float] = []
        false_negative_scores: list[float] = []
        exact_match_scores: list[float] = []
        retrieved_counts: list[float] = []

        for result in retrieval_results:
            retrieved_counts.append(float(result.result_count))

            if result.exact_identifier_match is not None:
                exact_match_scores.append(
                    1.0 if result.exact_identifier_match else 0.0
                )

            diagnostics = result.diagnostics or {}
            false_positives = diagnostics.get("false_positives") or []
            false_negatives = diagnostics.get("false_negatives") or []
            expected = result.expected_identifiers or []
            retrieved = result.retrieved_identifiers or []

            if expected:
                denom_fp = max(len(retrieved), 1)
                false_positive_scores.append(
                    len(false_positives) / float(denom_fp)
                )
                denom_fn = max(len(expected), 1)
                false_negative_scores.append(
                    len(false_negatives) / float(denom_fn)
                )

        category_buckets: dict[str, list[RetrievalEvaluationResult]] = {}
        for result in retrieval_results:
            category = result.category or "uncategorized"
            category_buckets.setdefault(category, []).append(result)

        category_metrics: dict[str, dict[str, float]] = {}
        for category, bucket in sorted(category_buckets.items()):
            category_metrics[category] = {
                "case_count": float(len(bucket)),
                "hit_at_1": mean(
                    [1.0 if item.hit_at_1 else 0.0 for item in bucket]
                ),
                "hit_at_5": mean(
                    [1.0 if item.hit_at_5 else 0.0 for item in bucket]
                ),
                "mean_reciprocal_rank": mean(
                    [item.reciprocal_rank for item in bucket]
                ),
                "mean_latency_ms": mean([item.latency_ms for item in bucket]),
                "mean_context_length": mean(
                    [float(item.context_length) for item in bucket]
                ),
            }

        return EvaluationSummary(
            dataset_name=dataset.name,
            dataset_version=dataset.version,
            total_cases=len(dataset.cases),
            retrieval_cases=retrieval_count,
            answer_cases=answer_count,
            hit_at_1=hit_at_1,
            hit_at_3=hit_at_3,
            hit_at_5=hit_at_5,
            mean_reciprocal_rank=mean_rr,
            answer_term_recall=mean(term_recalls),
            source_accuracy=mean(source_scores),
            refusal_accuracy=mean(refusal_scores),
            grounded_response_rate=mean(grounded_scores),
            retrieval_latency_mean_ms=mean(retrieval_latencies),
            retrieval_latency_p95_ms=percentile(retrieval_latencies, 95.0),
            answer_latency_mean_ms=mean(answer_latencies),
            answer_latency_p95_ms=percentile(answer_latencies, 95.0),
            mean_context_length=mean(context_lengths),
            confidence_high_rate=mean(
                [1.0 if level == "HIGH" else 0.0 for level in confidence_levels]
            ),
            confidence_medium_rate=mean(
                [
                    1.0 if level == "MEDIUM" else 0.0
                    for level in confidence_levels
                ]
            ),
            confidence_low_rate=mean(
                [1.0 if level == "LOW" else 0.0 for level in confidence_levels]
            ),
            confidence_accuracy=confidence_accuracy,
            false_positive_rate=mean(false_positive_scores),
            false_negative_rate=mean(false_negative_scores),
            exact_identifier_match_rate=mean(exact_match_scores),
            mean_retrieved_documents=mean(retrieved_counts),
            confidence_calibration=confidence_accuracy,
            category_metrics=category_metrics,
            failures=failures,
        )
