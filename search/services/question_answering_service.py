from __future__ import annotations

import logging
from typing import Any

from search.prompts.engineering_prompt import EngineeringPromptBuilder
from search.services.answer_generator import DrawingAnswerGenerator
from search.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

NO_EVIDENCE_ANSWER = (
    "The available indexed drawing context does not contain enough "
    "information to answer this question."
)


class DrawingQuestionAnsweringService:
    """Grounded question answering over indexed engineering drawing data."""

    def __init__(
        self,
        retrieval_service: RetrievalService,
        answer_generator: DrawingAnswerGenerator | None = None,
        prompt_builder: type[EngineeringPromptBuilder] | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.answer_generator = answer_generator
        self.prompt_builder = prompt_builder or EngineeringPromptBuilder

    @staticmethod
    def _extract_sources(
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []

        for result in results:
            sources.append(
                {
                    "rank": result.get("rank"),
                    "drawing_id": result.get("drawing_id"),
                    "drawing_number": result.get("drawing_number"),
                    "revision": result.get("revision"),
                    "filename": result.get("filename"),
                    "title": result.get("title"),
                    "bm25_score": result.get("bm25_score"),
                    "fts_score": result.get("fts_score"),
                    "matched_terms": result.get("matched_terms", []),
                }
            )

        return sources

    @staticmethod
    def _format_no_evidence_response(
        question: str,
        retrieval: dict[str, Any],
    ) -> dict[str, Any]:
        response = {
            "question": question,
            "answer": NO_EVIDENCE_ANSWER,
            "grounded": False,
            "candidate_count": retrieval["candidate_count"],
            "result_count": retrieval["result_count"],
            "sources": [],
            "context": retrieval.get("context", ""),
        }

        for key in (
            "confidence_score",
            "confidence_level",
            "confidence_signals",
            "confidence_explanation",
            "preprocessed_query",
        ):
            if key in retrieval:
                response[key] = retrieval[key]

        return response

    @staticmethod
    def _has_exact_identifier_match(retrieval: dict[str, Any]) -> bool:
        for result in retrieval.get("results", []):
            if result.get("exact_identifier_match"):
                return True

        signals = retrieval.get("confidence_signals") or {}
        return bool(signals.get("exact_identifier_match"))

    def answer(
        self,
        question: str,
        candidate_limit: int = 30,
        top_k: int = 5,
        max_context_characters: int = 16000,
    ) -> dict[str, Any]:
        if not isinstance(question, str):
            raise TypeError("question must be a string.")

        if not question.strip():
            raise ValueError("question must not be blank.")

        logger.debug(
            "Answering question with candidate_limit=%s top_k=%s",
            candidate_limit,
            top_k,
        )

        retrieval = self.retrieval_service.retrieve(
            query=question,
            candidate_limit=candidate_limit,
            top_k=top_k,
            max_context_characters=max_context_characters,
        )

        low_confidence_no_match = (
            retrieval.get("confidence_level") == "LOW"
            and not self._has_exact_identifier_match(retrieval)
        )

        if (
            retrieval["result_count"] == 0
            or not retrieval.get("context", "").strip()
            or low_confidence_no_match
        ):
            logger.debug(
                "No retrieval evidence for question; skipping LLM call."
            )
            return self._format_no_evidence_response(question, retrieval)

        if self.answer_generator is None:
            self.answer_generator = DrawingAnswerGenerator()

        prompt = self.prompt_builder.build(
            question=question,
            context=retrieval["context"],
        )

        answer_text = self.answer_generator.generate(prompt)

        response = {
            "question": question,
            "answer": answer_text,
            "grounded": True,
            "candidate_count": retrieval["candidate_count"],
            "result_count": retrieval["result_count"],
            "sources": self._extract_sources(retrieval["results"]),
            "context": retrieval["context"],
        }

        for key in (
            "confidence_score",
            "confidence_level",
            "confidence_signals",
            "confidence_explanation",
            "preprocessed_query",
        ):
            if key in retrieval:
                response[key] = retrieval[key]

        return response
