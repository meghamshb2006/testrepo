from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from search.database import SearchDatabase
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository
from search.services.answer_generator import DrawingAnswerGenerator
from search.services.question_answering_service import (
    NO_EVIDENCE_ANSWER,
    DrawingQuestionAnsweringService,
)
from search.services.retrieval_service import RetrievalService


class _RecordingCompletions:
    def __init__(self) -> None:
        self.last_prompt: str | None = None

    def create(self, **kwargs):
        self.last_prompt = kwargs["messages"][1]["content"]
        message = SimpleNamespace(content="Aluminium 6061-T6.")
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _RecordingChat:
    def __init__(self) -> None:
        self.completions = _RecordingCompletions()


class _RecordingClient:
    def __init__(self) -> None:
        self.chat = _RecordingChat()


@pytest.fixture
def qa_service(
    tmp_path: Path,
) -> tuple[DrawingQuestionAnsweringService, _RecordingClient]:
    database = SearchDatabase(str(tmp_path / "qa_integration.db"))
    database.initialize()
    repository = SearchRepository(database)

    now = datetime.now(timezone.utc)
    repository.upsert(
        SearchDocument(
            drawing_id="drawing-001",
            filename="mounting_bracket.pdf",
            drawing_number="DR-1023",
            revision="C",
            title="Mounting Bracket",
            material="Aluminium 6061-T6",
            finish="Anodised",
            units="mm",
            part_numbers="BR-1001",
            dimensions_text="120 mm hole diameter 10 mm",
            tolerances_text="ISO-2768-mK plusminus 0.05 mm",
            notes_text="Surface finish anodised",
            searchable_text=(
                "DR-1023 mounting bracket aluminium 6061-T6 BR-1001 "
                "120 mm ISO-2768-mK anodised revision C"
            ),
            created_at=now,
            updated_at=now,
        )
    )

    client = _RecordingClient()
    retrieval_service = RetrievalService(repository=repository)
    answer_generator = DrawingAnswerGenerator(
        client=client,
        model="test-model",
    )
    service = DrawingQuestionAnsweringService(
        retrieval_service=retrieval_service,
        answer_generator=answer_generator,
    )

    yield service, client

    database.close()


def test_integration_answers_with_real_retrieval_and_mock_llm(
    qa_service: tuple[DrawingQuestionAnsweringService, _RecordingClient],
) -> None:
    service, client = qa_service

    response = service.answer(
        "What material is specified for BR-1001?",
        candidate_limit=10,
        top_k=3,
    )

    assert response["grounded"] is True
    assert response["result_count"] >= 1
    assert response["sources"]
    assert response["sources"][0]["drawing_id"] == "drawing-001"
    assert "6061-T6" in response["context"] or "6061-t6" in response["context"].lower()

    prompt = client.chat.completions.last_prompt
    assert prompt is not None
    assert "BR-1001" in prompt
    assert "6061-T6" in prompt or "6061-t6" in prompt.lower()


def test_integration_no_match_skips_llm(
    qa_service: tuple[DrawingQuestionAnsweringService, _RecordingClient],
) -> None:
    service, client = qa_service

    response = service.answer(
        "What is the titanium alloy specification for part ZZ-9999?",
        candidate_limit=10,
        top_k=3,
    )

    assert response["grounded"] is False
    assert response["answer"] == NO_EVIDENCE_ANSWER
    assert response["sources"] == []
    assert client.chat.completions.last_prompt is None
