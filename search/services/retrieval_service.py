from __future__ import annotations

from typing import Any

from search.context.context_builder import ContextBuilder
from search.engines.bm25_engine import BM25SearchEngine
from search.repositories.search_repository import SearchRepository


class RetrievalService:
    """Two-stage retrieval: FTS5 candidate selection followed by BM25 reranking."""

    def __init__(
        self,
        repository: SearchRepository,
        bm25_engine: BM25SearchEngine | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self.repository = repository
        self.bm25_engine = bm25_engine or BM25SearchEngine(
            repository=repository,
        )
        self.context_builder = context_builder or ContextBuilder()

    def retrieve(
        self,
        query: str,
        candidate_limit: int = 30,
        top_k: int = 5,
        max_context_characters: int = 16000,
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

        candidates = self.repository.search_fts(
            query,
            limit=candidate_limit,
        )

        if not candidates:
            return {
                "query": query,
                "candidate_count": 0,
                "result_count": 0,
                "results": [],
                "context": "",
            }

        self.bm25_engine.build_index(candidates)
        results = self.bm25_engine.search(query, top_k=top_k)
        context = self.context_builder.build_context(
            results,
            max_documents=top_k,
            max_characters=max_context_characters,
        )

        return {
            "query": query,
            "candidate_count": len(candidates),
            "result_count": len(results),
            "results": results,
            "context": context,
        }
