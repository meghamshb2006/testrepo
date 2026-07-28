from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from search.database import SearchDatabase
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository
from search.services.retrieval_logger import RetrievalLogger
from search.services.retrieval_service import RetrievalService


def _seed(repository: SearchRepository) -> None:
    now = datetime.now(timezone.utc)
    repository.upsert(
        SearchDocument(
            drawing_id="drawing-001",
            filename="mounting_bracket.pdf",
            drawing_number="DR-1023",
            revision="C",
            material="Aluminium 6061-T6",
            part_numbers="BR-1001",
            searchable_text=(
                "DR-1023 mounting bracket aluminium 6061-T6 BR-1001"
            ),
            created_at=now,
            updated_at=now,
        )
    )


def test_include_trace_false_omits_trace(tmp_path: Path) -> None:
    database = SearchDatabase(str(tmp_path / "trace.db"))
    database.initialize()
    repository = SearchRepository(database)
    _seed(repository)
    service = RetrievalService(repository=repository)

    response = service.retrieve("DR-1023", include_trace=False)

    assert "retrieval_trace" not in response
    assert "confidence_explanation" in response
    database.close()


def test_include_trace_true_returns_serializable_trace(
    tmp_path: Path,
) -> None:
    database = SearchDatabase(str(tmp_path / "trace.db"))
    database.initialize()
    repository = SearchRepository(database)
    _seed(repository)
    service = RetrievalService(repository=repository)

    response = service.retrieve("Find drawing DR-1023", include_trace=True)
    trace = response["retrieval_trace"]

    assert trace["original_query"] == "Find drawing DR-1023"
    assert "stage_latencies_ms" in trace
    assert "preprocess" in trace["stage_latencies_ms"]
    assert isinstance(trace["score_breakdowns"], list)
    assert response["confidence_explanation"]
    database.close()


def test_retrieval_logger_disabled_by_default() -> None:
    logger = MagicMock()
    retrieval_logger = RetrievalLogger(
        enabled=False,
        logger=logger,
    )
    retrieval_logger.log_retrieval(
        query="q",
        normalized_query="q",
        identifiers=[],
        result_count=0,
        confidence_level="LOW",
        confidence_score=0.0,
        latency_ms=1.0,
    )
    logger.log.assert_not_called()


def test_retrieval_logger_emits_when_enabled() -> None:
    logger = MagicMock()
    retrieval_logger = RetrievalLogger(
        enabled=True,
        level="INFO",
        logger=logger,
    )
    retrieval_logger.log_retrieval(
        query="DR-1023",
        normalized_query="DR-1023",
        identifiers=[{"value": "DR-1023"}],
        result_count=1,
        confidence_level="HIGH",
        confidence_score=0.9,
        latency_ms=12.5,
        drawing_ids=["drawing-001"],
        confidence_explanation=["Exact identifier match"],
    )
    logger.log.assert_called_once()
