from __future__ import annotations

import time

from evaluation.metrics import normalise_identifier
from evaluation.schemas import BenchmarkCase, RetrievalEvaluationResult
from search.diagnostics.evaluation_diagnostics import EvaluationDiagnostics
from search.services.retrieval_service import RetrievalService


class RetrievalEvaluator:
    """Evaluates retrieval quality for a single benchmark case."""

    def __init__(self, retrieval_service: RetrievalService) -> None:
        self.retrieval_service = retrieval_service

    @staticmethod
    def _expected_identifiers(case: BenchmarkCase) -> list[str]:
        identifiers: list[str] = []

        for value in (
            case.expected_drawing_ids
            + case.expected_drawing_numbers
            + case.expected_filenames
        ):
            if value and value.strip():
                identifiers.append(value.strip())

        return identifiers

    @staticmethod
    def _result_identifiers(result: dict) -> list[str]:
        identifiers: list[str] = []

        for field_name in ("drawing_id", "drawing_number", "filename"):
            value = result.get(field_name)

            if value is None:
                continue

            text = str(value).strip()

            if text:
                identifiers.append(text)

        return identifiers

    @classmethod
    def _retrieved_identifiers(cls, results: list[dict]) -> list[str]:
        identifiers: list[str] = []
        seen: set[str] = set()

        for result in results:
            for text in cls._result_identifiers(result):
                key = text.casefold()

                if key in seen:
                    continue

                seen.add(key)
                identifiers.append(text)

        return identifiers

    @classmethod
    def _result_matches(
        cls,
        result: dict,
        expected_normalised: set[str],
    ) -> bool:
        for text in cls._result_identifiers(result):
            if normalise_identifier(text) in expected_normalised:
                return True

        return False

    @classmethod
    def _hit_at_k(
        cls,
        results: list[dict],
        expected: list[str],
        k: int,
    ) -> bool:
        if not expected:
            return False

        expected_normalised = {
            normalise_identifier(item)
            for item in expected
            if item and str(item).strip()
        }

        if not expected_normalised:
            return False

        for result in results[:k]:
            if cls._result_matches(result, expected_normalised):
                return True

        return False

    @classmethod
    def _reciprocal_rank(
        cls,
        results: list[dict],
        expected: list[str],
    ) -> float:
        if not expected:
            return 0.0

        expected_normalised = {
            normalise_identifier(item)
            for item in expected
            if item and str(item).strip()
        }

        if not expected_normalised:
            return 0.0

        for index, result in enumerate(results, start=1):
            if cls._result_matches(result, expected_normalised):
                return 1.0 / float(index)

        return 0.0

    def evaluate_case(
        self,
        case: BenchmarkCase,
        default_candidate_limit: int = 30,
        default_top_k: int = 5,
        default_max_context_characters: int = 16000,
    ) -> RetrievalEvaluationResult:
        expected = self._expected_identifiers(case)
        candidate_limit = case.candidate_limit or default_candidate_limit
        top_k = case.top_k or default_top_k
        max_context_characters = (
            case.max_context_characters or default_max_context_characters
        )

        started = time.perf_counter()

        try:
            retrieval = self.retrieval_service.retrieve(
                query=case.question,
                candidate_limit=candidate_limit,
                top_k=top_k,
                max_context_characters=max_context_characters,
                include_trace=True,
            )
            latency_ms = (time.perf_counter() - started) * 1000.0
            results = retrieval["results"]
            retrieved = self._retrieved_identifiers(results)
            confidence_level = retrieval.get("confidence_level")
            expected_confidence = case.expected_confidence_level
            confidence_match = None

            if expected_confidence is not None and confidence_level is not None:
                confidence_match = (
                    str(confidence_level).upper() == expected_confidence
                )

            exact_match = None
            if results:
                exact_match = bool(results[0].get("exact_identifier_match"))

            diagnostics = EvaluationDiagnostics.build_case_diagnostics(
                trace=retrieval.get("retrieval_trace"),
                expected_identifiers=expected,
                retrieved_identifiers=retrieved,
                confidence_explanation=retrieval.get(
                    "confidence_explanation"
                ),
            )

            return RetrievalEvaluationResult(
                case_id=case.case_id,
                question=case.question,
                expected_identifiers=expected,
                retrieved_identifiers=retrieved,
                hit_at_1=self._hit_at_k(results, expected, 1),
                hit_at_3=self._hit_at_k(results, expected, 3),
                hit_at_5=self._hit_at_k(results, expected, 5),
                reciprocal_rank=self._reciprocal_rank(results, expected),
                result_count=retrieval["result_count"],
                candidate_count=retrieval["candidate_count"],
                latency_ms=latency_ms,
                category=case.category,
                context_length=len(retrieval.get("context") or ""),
                confidence_score=retrieval.get("confidence_score"),
                confidence_level=confidence_level,
                expected_confidence_level=expected_confidence,
                confidence_level_match=confidence_match,
                exact_identifier_match=exact_match,
                diagnostics=diagnostics,
            )

        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000.0

            return RetrievalEvaluationResult(
                case_id=case.case_id,
                question=case.question,
                expected_identifiers=expected,
                retrieved_identifiers=[],
                hit_at_1=False,
                hit_at_3=False,
                hit_at_5=False,
                reciprocal_rank=0.0,
                result_count=0,
                candidate_count=0,
                latency_ms=latency_ms,
                error=str(exc),
                category=case.category,
            )
