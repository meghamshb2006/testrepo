from __future__ import annotations

from evaluation.metrics import normalise_text


class RefusalEvaluator:
    """Deterministic refusal detection for unanswerable questions."""

    DEFAULT_REFUSAL_PHRASES = (
        "does not contain enough information",
        "cannot be determined",
        "insufficient context",
        "not available in the indexed drawing context",
        "available indexed drawing context does not contain",
    )

    @classmethod
    def is_correct_refusal(
        cls,
        answer: str,
        grounded: bool,
    ) -> bool:
        if grounded:
            return False

        if not isinstance(answer, str) or not answer.strip():
            return False

        normalised_answer = normalise_text(answer)

        for phrase in cls.DEFAULT_REFUSAL_PHRASES:
            if normalise_text(phrase) in normalised_answer:
                return True

        return False
