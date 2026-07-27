from __future__ import annotations

from evaluation.evaluators.refusal_evaluator import RefusalEvaluator
from search.services.question_answering_service import NO_EVIDENCE_ANSWER


def test_correct_refusal_phrase() -> None:
    assert RefusalEvaluator.is_correct_refusal(
        NO_EVIDENCE_ANSWER,
        grounded=False,
    )


def test_grounded_true_is_not_refusal() -> None:
    assert not RefusalEvaluator.is_correct_refusal(
        NO_EVIDENCE_ANSWER,
        grounded=True,
    )


def test_factual_not_is_not_refusal() -> None:
    assert not RefusalEvaluator.is_correct_refusal(
        "The part is not stainless steel; it is aluminium.",
        grounded=False,
    )


def test_cannot_be_determined_phrase() -> None:
    assert RefusalEvaluator.is_correct_refusal(
        "The answer cannot be determined from the available context.",
        grounded=False,
    )
