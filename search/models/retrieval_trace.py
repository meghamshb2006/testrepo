"""Serializable retrieval observability trace for developers and evaluation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RetrievedDocumentTrace(BaseModel):
    drawing_id: str | None = None
    drawing_number: str | None = None
    rank: int | None = None
    bm25_score: float | None = None
    exact_identifier_match: bool = False
    matched_identifiers: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)


class RetrievalTrace(BaseModel):
    original_query: str
    normalized_query: str = ""
    fts_query: str = ""
    query_tokens: list[str] = Field(default_factory=list)
    residual_tokens: list[str] = Field(default_factory=list)
    detected_identifiers: list[dict[str, Any]] = Field(default_factory=list)
    candidate_count: int = 0
    result_count: int = 0
    retrieved_documents: list[RetrievedDocumentTrace] = Field(
        default_factory=list
    )
    bm25_scores: list[float] = Field(default_factory=list)
    confidence_score: float = 0.0
    confidence_level: str = "LOW"
    confidence_explanation: list[str] = Field(default_factory=list)
    score_breakdowns: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: float = 0.0
    stage_latencies_ms: dict[str, float] = Field(default_factory=dict)
    candidate_drawing_ids: list[str] = Field(default_factory=list)
    preprocessing_rules_applied: list[str] = Field(default_factory=list)
    error: str | None = None
