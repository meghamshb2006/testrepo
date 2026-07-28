from __future__ import annotations

import time
from typing import Any

from app.config import (
    RETRIEVAL_CONFIDENCE_HIGH_THRESHOLD,
    RETRIEVAL_CONFIDENCE_MEDIUM_THRESHOLD,
    RETRIEVAL_EXACT_IDENTIFIER_BOOST_WEIGHT,
    RETRIEVAL_LOG_LEVEL,
    RETRIEVAL_OBSERVABILITY_LOGGING,
)
from search.context.context_builder import ContextBuilder
from search.engines.bm25_engine import BM25SearchEngine
from search.repositories.search_repository import SearchRepository
from search.services.identifier_matcher import ExactIdentifierBooster
from search.services.query_preprocessor import (
    EngineeringQueryPreprocessor,
    PreprocessedQuery,
)
from search.services.retrieval_confidence import RetrievalConfidenceEstimator
from search.services.retrieval_logger import RetrievalLogger
from search.services.retrieval_trace_builder import RetrievalTraceBuilder


class RetrievalService:
    """Two-stage retrieval with query preprocessing and confidence estimation."""

    def __init__(
        self,
        repository: SearchRepository,
        bm25_engine: BM25SearchEngine | None = None,
        context_builder: ContextBuilder | None = None,
        query_preprocessor: EngineeringQueryPreprocessor | None = None,
        identifier_booster: ExactIdentifierBooster | None = None,
        confidence_estimator: RetrievalConfidenceEstimator | None = None,
        retrieval_logger: RetrievalLogger | None = None,
    ) -> None:
        self.repository = repository
        self.bm25_engine = bm25_engine or BM25SearchEngine(
            repository=repository,
        )
        self.context_builder = context_builder or ContextBuilder()
        self.query_preprocessor = (
            query_preprocessor or EngineeringQueryPreprocessor()
        )
        self.identifier_booster = (
            identifier_booster or ExactIdentifierBooster()
        )
        self.confidence_estimator = confidence_estimator or (
            RetrievalConfidenceEstimator(
                high_threshold=RETRIEVAL_CONFIDENCE_HIGH_THRESHOLD,
                medium_threshold=RETRIEVAL_CONFIDENCE_MEDIUM_THRESHOLD,
                weight_exact_match=RETRIEVAL_EXACT_IDENTIFIER_BOOST_WEIGHT,
            )
        )
        self.retrieval_logger = retrieval_logger or RetrievalLogger(
            enabled=RETRIEVAL_OBSERVABILITY_LOGGING,
            level=RETRIEVAL_LOG_LEVEL,
        )
        self.trace_builder = RetrievalTraceBuilder()

    @staticmethod
    def _preprocessed_payload(
        preprocessed: PreprocessedQuery,
    ) -> dict[str, Any]:
        return {
            "normalized_query": preprocessed.normalized_query,
            "fts_query": preprocessed.fts_query,
            "residual_tokens": preprocessed.residual_tokens,
            "identifiers": [
                {
                    "value": item.value,
                    "type": item.identifier_type,
                    "raw": item.raw,
                }
                for item in preprocessed.identifiers
            ],
        }

    def retrieve(
        self,
        query: str,
        candidate_limit: int = 30,
        top_k: int = 5,
        max_context_characters: int = 16000,
        include_trace: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(query, str):
            raise TypeError("query must be a string.")

        if not query.strip():
            raise ValueError("query must not be blank.")

        if not isinstance(candidate_limit, int) or candidate_limit < 1:
            raise ValueError("candidate_limit must be an integer >= 1.")

        if not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be an integer >= 1.")

        if (
            not isinstance(max_context_characters, int)
            or max_context_characters < 1
        ):
            raise ValueError(
                "max_context_characters must be an integer >= 1."
            )

        if top_k > candidate_limit:
            raise ValueError("top_k must not exceed candidate_limit.")

        started = time.perf_counter()
        stage_latencies_ms: dict[str, float] = {}

        stage_started = time.perf_counter()
        preprocessed = self.query_preprocessor.preprocess(query)
        fts_query = self._build_fts_query(preprocessed)
        query_tokens = self.bm25_engine.processor.preprocess(
            preprocessed.normalized_query or query
        )
        stage_latencies_ms["preprocess"] = (
            time.perf_counter() - stage_started
        ) * 1000.0

        stage_started = time.perf_counter()
        candidates = self.repository.search_fts(
            fts_query,
            limit=candidate_limit,
        )
        stage_latencies_ms["fts"] = (
            time.perf_counter() - stage_started
        ) * 1000.0

        if not candidates:
            confidence = self.confidence_estimator.estimate(
                results=[],
                preprocessed=preprocessed,
                context="",
                candidate_count=0,
            )
            latency_ms = (time.perf_counter() - started) * 1000.0
            response = {
                "query": query,
                "candidate_count": 0,
                "result_count": 0,
                "results": [],
                "context": "",
                "confidence_score": confidence.confidence_score,
                "confidence_level": confidence.confidence_level,
                "confidence_signals": confidence.confidence_signals,
                "confidence_explanation": confidence.confidence_explanation,
                "preprocessed_query": self._preprocessed_payload(
                    preprocessed
                ),
            }
            self._finalize_observability(
                response=response,
                include_trace=include_trace,
                original_query=query,
                preprocessed=preprocessed,
                fts_query=fts_query,
                query_tokens=query_tokens,
                candidates=[],
                results=[],
                confidence=confidence,
                stage_latencies_ms=stage_latencies_ms,
                latency_ms=latency_ms,
            )
            return response

        search_query = preprocessed.normalized_query or query

        stage_started = time.perf_counter()
        self.bm25_engine.build_index(candidates)
        results = self.bm25_engine.search(search_query, top_k=top_k)
        stage_latencies_ms["bm25"] = (
            time.perf_counter() - stage_started
        ) * 1000.0

        stage_started = time.perf_counter()
        results = self.identifier_booster.boost(
            results,
            preprocessed.identifiers,
        )
        stage_latencies_ms["boost"] = (
            time.perf_counter() - stage_started
        ) * 1000.0

        stage_started = time.perf_counter()
        context = self.context_builder.build_context(
            results,
            max_documents=top_k,
            max_characters=max_context_characters,
        )
        stage_latencies_ms["context"] = (
            time.perf_counter() - stage_started
        ) * 1000.0

        stage_started = time.perf_counter()
        confidence = self.confidence_estimator.estimate(
            results=results,
            preprocessed=preprocessed,
            context=context,
            candidate_count=len(candidates),
        )
        stage_latencies_ms["confidence"] = (
            time.perf_counter() - stage_started
        ) * 1000.0

        latency_ms = (time.perf_counter() - started) * 1000.0
        response = {
            "query": query,
            "candidate_count": len(candidates),
            "result_count": len(results),
            "results": results,
            "context": context,
            "confidence_score": confidence.confidence_score,
            "confidence_level": confidence.confidence_level,
            "confidence_signals": confidence.confidence_signals,
            "confidence_explanation": confidence.confidence_explanation,
            "preprocessed_query": self._preprocessed_payload(preprocessed),
        }
        self._finalize_observability(
            response=response,
            include_trace=include_trace,
            original_query=query,
            preprocessed=preprocessed,
            fts_query=fts_query,
            query_tokens=query_tokens,
            candidates=candidates,
            results=results,
            confidence=confidence,
            stage_latencies_ms=stage_latencies_ms,
            latency_ms=latency_ms,
        )
        return response

    def _finalize_observability(
        self,
        *,
        response: dict[str, Any],
        include_trace: bool,
        original_query: str,
        preprocessed: PreprocessedQuery,
        fts_query: str,
        query_tokens: list[str],
        candidates: list[dict[str, Any]],
        results: list[dict[str, Any]],
        confidence: Any,
        stage_latencies_ms: dict[str, float],
        latency_ms: float,
        error: str | None = None,
    ) -> None:
        preprocessed_payload = response["preprocessed_query"]
        self.retrieval_logger.log_retrieval(
            query=original_query,
            normalized_query=preprocessed.normalized_query,
            identifiers=preprocessed_payload["identifiers"],
            result_count=response["result_count"],
            confidence_level=confidence.confidence_level,
            confidence_score=confidence.confidence_score,
            latency_ms=latency_ms,
            drawing_ids=[
                str(result.get("drawing_id"))
                for result in results
                if result.get("drawing_id") is not None
            ],
            confidence_explanation=confidence.confidence_explanation,
            error=error,
        )

        if not include_trace:
            return

        trace = self.trace_builder.build(
            original_query=original_query,
            preprocessed=preprocessed,
            fts_query=fts_query,
            query_tokens=query_tokens,
            candidates=candidates,
            results=results,
            confidence_score=confidence.confidence_score,
            confidence_level=confidence.confidence_level,
            confidence_explanation=confidence.confidence_explanation,
            stage_latencies_ms=stage_latencies_ms,
            latency_ms=latency_ms,
            error=error,
        )
        response["retrieval_trace"] = trace.model_dump(mode="json")

    def _build_fts_query(self, preprocessed: PreprocessedQuery) -> str:
        parts: list[str] = []

        for identifier in preprocessed.identifiers:
            quoted = f'"{identifier.value}"'

            if quoted not in parts:
                parts.append(quoted)

        residual_source = " ".join(preprocessed.residual_tokens)

        if residual_source.strip():
            nltk_tokens = self.bm25_engine.processor.preprocess(
                residual_source
            )
        elif not preprocessed.identifiers:
            nltk_tokens = self.bm25_engine.processor.preprocess(
                preprocessed.original_query
            )
        else:
            nltk_tokens = []

        for token in nltk_tokens:
            if token not in parts:
                parts.append(token)

        if not parts:
            return preprocessed.fts_query or preprocessed.normalized_query

        if len(parts) == 1:
            return parts[0]

        return " OR ".join(parts)
