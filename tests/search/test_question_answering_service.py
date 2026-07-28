from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from search.prompts.engineering_prompt import EngineeringPromptBuilder
from search.services.answer_generator import DrawingAnswerGenerator
from search.services.question_answering_service import (
    NO_EVIDENCE_ANSWER,
    DrawingQuestionAnsweringService,
)


@pytest.fixture
def retrieval_with_evidence() -> dict:
    return {
        "query": "What material is specified for BR-1001?",
        "candidate_count": 2,
        "result_count": 1,
        "results": [
            {
                "rank": 1,
                "drawing_id": "drawing-001",
                "drawing_number": "DR-1023",
                "revision": "C",
                "filename": "mounting_bracket.pdf",
                "title": "Mounting Bracket",
                "material": "Aluminium 6061-T6",
                "bm25_score": 1.23,
                "fts_score": -2.5,
                "matched_terms": ["br-1001", "6061-t6"],
                "searchable_text": "BR-1001 Aluminium 6061-T6",
            }
        ],
        "context": (
            "Retrieved Drawing 1\n"
            "Drawing Number: DR-1023\n"
            "Material: Aluminium 6061-T6"
        ),
    }


@pytest.fixture
def retrieval_without_evidence() -> dict:
    return {
        "query": "unknown widget",
        "candidate_count": 0,
        "result_count": 0,
        "results": [],
        "context": "",
    }


def test_answer_calls_generator_when_evidence_exists(
    retrieval_with_evidence: dict,
) -> None:
    retrieval_service = MagicMock()
    retrieval_service.retrieve.return_value = retrieval_with_evidence

    answer_generator = MagicMock()
    answer_generator.generate.return_value = (
        "The specified material is aluminium alloy 6061-T6."
    )

    service = DrawingQuestionAnsweringService(
        retrieval_service=retrieval_service,
        answer_generator=answer_generator,
    )

    response = service.answer("What material is specified for BR-1001?")

    retrieval_service.retrieve.assert_called_once_with(
        query="What material is specified for BR-1001?",
        candidate_limit=30,
        top_k=5,
        max_context_characters=16000,
    )
    answer_generator.generate.assert_called_once()
    prompt = answer_generator.generate.call_args[0][0]
    assert "BR-1001" in prompt or "6061-T6" in prompt
    assert response["grounded"] is True
    assert response["answer"].startswith("The specified material")
    assert response["sources"][0]["drawing_number"] == "DR-1023"
    assert "prompt" not in response


def test_no_evidence_skips_llm(
    retrieval_without_evidence: dict,
) -> None:
    retrieval_service = MagicMock()
    retrieval_service.retrieve.return_value = retrieval_without_evidence

    answer_generator = MagicMock()

    service = DrawingQuestionAnsweringService(
        retrieval_service=retrieval_service,
        answer_generator=answer_generator,
    )

    response = service.answer("What material is used for widget Z?")

    answer_generator.generate.assert_not_called()
    assert response["grounded"] is False
    assert response["answer"] == NO_EVIDENCE_ANSWER
    assert response["sources"] == []


def test_no_evidence_does_not_create_answer_generator(
    retrieval_without_evidence: dict,
) -> None:
    retrieval_service = MagicMock()
    retrieval_service.retrieve.return_value = retrieval_without_evidence

    service = DrawingQuestionAnsweringService(
        retrieval_service=retrieval_service,
    )

    with patch(
        "search.services.question_answering_service.DrawingAnswerGenerator"
    ) as generator_cls:
        response = service.answer("What material is used for widget Z?")

    generator_cls.assert_not_called()
    assert response["grounded"] is False
    assert service.answer_generator is None


def test_evidence_path_lazily_creates_answer_generator(
    retrieval_with_evidence: dict,
) -> None:
    retrieval_service = MagicMock()
    retrieval_service.retrieve.return_value = retrieval_with_evidence

    service = DrawingQuestionAnsweringService(
        retrieval_service=retrieval_service,
    )

    created_generator = MagicMock()
    created_generator.generate.return_value = "Answer text."

    with patch(
        "search.services.question_answering_service.DrawingAnswerGenerator",
        return_value=created_generator,
    ) as generator_cls:
        response = service.answer("What material is specified for BR-1001?")

    generator_cls.assert_called_once_with()
    created_generator.generate.assert_called_once()
    assert service.answer_generator is created_generator
    assert response["grounded"] is True


def test_structured_sources_include_scores(
    retrieval_with_evidence: dict,
) -> None:
    retrieval_service = MagicMock()
    retrieval_service.retrieve.return_value = retrieval_with_evidence

    answer_generator = MagicMock()
    answer_generator.generate.return_value = "Answer text."

    service = DrawingQuestionAnsweringService(
        retrieval_service=retrieval_service,
        answer_generator=answer_generator,
    )

    response = service.answer("What material is specified for BR-1001?")
    source = response["sources"][0]

    assert source["bm25_score"] == 1.23
    assert source["fts_score"] == -2.5
    assert source["matched_terms"] == ["br-1001", "6061-t6"]


def test_retrieval_parameters_forwarded(
    retrieval_with_evidence: dict,
) -> None:
    retrieval_service = MagicMock()
    retrieval_service.retrieve.return_value = retrieval_with_evidence

    answer_generator = MagicMock()
    answer_generator.generate.return_value = "Answer text."

    service = DrawingQuestionAnsweringService(
        retrieval_service=retrieval_service,
        answer_generator=answer_generator,
    )

    service.answer(
        "What material is specified for BR-1001?",
        candidate_limit=10,
        top_k=2,
        max_context_characters=500,
    )

    retrieval_service.retrieve.assert_called_once_with(
        query="What material is specified for BR-1001?",
        candidate_limit=10,
        top_k=2,
        max_context_characters=500,
    )


def test_invalid_question_rejected() -> None:
    service = DrawingQuestionAnsweringService(
        retrieval_service=MagicMock(),
        answer_generator=MagicMock(),
    )

    with pytest.raises(ValueError, match="blank"):
        service.answer("   ")


def test_low_confidence_without_exact_match_skips_llm(
    retrieval_with_evidence: dict,
) -> None:
    retrieval = dict(retrieval_with_evidence)
    retrieval["confidence_level"] = "LOW"
    retrieval["confidence_score"] = 0.2
    retrieval["confidence_signals"] = {"exact_identifier_match": False}
    retrieval["results"] = [
        {
            **retrieval_with_evidence["results"][0],
            "exact_identifier_match": False,
            "matched_identifiers": [],
        }
    ]

    retrieval_service = MagicMock()
    retrieval_service.retrieve.return_value = retrieval

    answer_generator = MagicMock()

    service = DrawingQuestionAnsweringService(
        retrieval_service=retrieval_service,
        answer_generator=answer_generator,
    )

    response = service.answer("vague question")

    answer_generator.generate.assert_not_called()
    assert response["grounded"] is False
    assert response["answer"] == NO_EVIDENCE_ANSWER
    assert response["confidence_level"] == "LOW"


def test_low_confidence_with_exact_match_still_answers(
    retrieval_with_evidence: dict,
) -> None:
    retrieval = dict(retrieval_with_evidence)
    retrieval["confidence_level"] = "LOW"
    retrieval["confidence_score"] = 0.4
    retrieval["results"] = [
        {
            **retrieval_with_evidence["results"][0],
            "exact_identifier_match": True,
            "matched_identifiers": ["BR-1001"],
        }
    ]

    retrieval_service = MagicMock()
    retrieval_service.retrieve.return_value = retrieval

    answer_generator = MagicMock()
    answer_generator.generate.return_value = "Answer text."

    service = DrawingQuestionAnsweringService(
        retrieval_service=retrieval_service,
        answer_generator=answer_generator,
    )

    response = service.answer("What material is specified for BR-1001?")

    answer_generator.generate.assert_called_once()
    assert response["grounded"] is True


def test_custom_prompt_builder_used(
    retrieval_with_evidence: dict,
) -> None:
    retrieval_service = MagicMock()
    retrieval_service.retrieve.return_value = retrieval_with_evidence

    prompt_builder = MagicMock()
    prompt_builder.build.return_value = "custom prompt"

    answer_generator = MagicMock()
    answer_generator.generate.return_value = "Answer text."

    service = DrawingQuestionAnsweringService(
        retrieval_service=retrieval_service,
        answer_generator=answer_generator,
        prompt_builder=prompt_builder,
    )

    service.answer("What material is specified for BR-1001?")

    prompt_builder.build.assert_called_once()
