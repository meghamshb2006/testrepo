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
            failures=failures,
        )
