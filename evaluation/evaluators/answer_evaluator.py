from __future__ import annotations

import time

from evaluation.evaluators.refusal_evaluator import RefusalEvaluator
from evaluation.metrics import (
    forbidden_term_matches,
    source_match,
    term_recall,
)
from evaluation.schemas import AnswerEvaluationResult, BenchmarkCase
from search.services.question_answering_service import (
    DrawingQuestionAnsweringService,
)


class AnswerEvaluator:
    """Evaluates grounded answer quality for a single benchmark case."""

    def __init__(
        self,
        qa_service: DrawingQuestionAnsweringService,
    ) -> None:
        self.qa_service = qa_service

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

    def evaluate_case(
        self,
        case: BenchmarkCase,
        default_candidate_limit: int = 30,
        default_top_k: int = 5,
        default_max_context_characters: int = 16000,
    ) -> AnswerEvaluationResult:
        candidate_limit = case.candidate_limit or default_candidate_limit
        top_k = case.top_k or default_top_k
        max_context_characters = (
            case.max_context_characters or default_max_context_characters
        )

        started = time.perf_counter()

        try:
            response = self.qa_service.answer(
                question=case.question,
                candidate_limit=candidate_limit,
                top_k=top_k,
                max_context_characters=max_context_characters,
            )
            latency_ms = (time.perf_counter() - started) * 1000.0

            answer = str(response.get("answer") or "")
            grounded = bool(response.get("grounded"))
            sources = response.get("sources") or []

            found, missing, _recall = term_recall(
                answer,
                case.expected_answer_terms,
            )
            forbidden = forbidden_term_matches(
                answer,
                case.forbidden_answer_terms,
            )
            expected_identifiers = self._expected_identifiers(case)

            if case.answerable:
                refusal_correct = None
                matched = source_match(sources, expected_identifiers)
            else:
                refusal_correct = RefusalEvaluator.is_correct_refusal(
                    answer=answer,
                    grounded=grounded,
                )
                matched = False

            return AnswerEvaluationResult(
                case_id=case.case_id,
                question=case.question,
                answer=answer,
                answerable=case.answerable,
                grounded=grounded,
                expected_terms_found=found,
                expected_terms_missing=missing,
                forbidden_terms_found=forbidden,
                source_match=matched,
                refusal_correct=refusal_correct,
                latency_ms=latency_ms,
                category=case.category,
            )

        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000.0

            return AnswerEvaluationResult(
                case_id=case.case_id,
                question=case.question,
                answer="",
                answerable=case.answerable,
                grounded=False,
                expected_terms_found=[],
                expected_terms_missing=list(case.expected_answer_terms),
                forbidden_terms_found=[],
                source_match=False,
                refusal_correct=False if not case.answerable else None,
                latency_ms=latency_ms,
                error=str(exc),
                category=case.category,
            )
