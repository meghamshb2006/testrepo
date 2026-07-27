from __future__ import annotations

from typing import Any, Mapping

from rank_bm25 import BM25Okapi

from search.engines.search_engine import SearchEngine
from search.repositories.search_repository import SearchRepository
from search.services.nltk_processor import NLTKProcessor


class BM25SearchEngine(SearchEngine):
    """
    Real BM25 search engine backed by SearchRepository documents.

    The index can be built from the full repository or from a supplied
    candidate document list for two-stage retrieval.
    """

    _RESULT_FIELDS = (
        "drawing_id",
        "filename",
        "drawing_number",
        "revision",
        "title",
        "material",
        "finish",
        "units",
        "part_numbers",
        "dimensions_text",
        "tolerances_text",
        "notes_text",
        "searchable_text",
    )

    def __init__(
        self,
        repository: SearchRepository,
        processor: NLTKProcessor | None = None,
    ) -> None:
        self.repository = repository
        self.processor = processor or NLTKProcessor()

        self._documents: list[Any] = []
        self._tokenised_corpus: list[list[str]] = []
        self._index: BM25Okapi | None = None

    @property
    def index_ready(self) -> bool:
        return (
            self._index is not None
            and len(self._documents) > 0
            and len(self._tokenised_corpus) > 0
        )

    @staticmethod
    def _document_to_mapping(document: Any) -> Mapping[str, Any]:
        if isinstance(document, Mapping):
            return document

        if hasattr(document, "model_dump"):
            return document.model_dump()

        if hasattr(document, "dict"):
            return document.dict()

        raise TypeError(
            "Repository documents must be mappings or Pydantic models."
        )

    @classmethod
    def _get_value(
        cls,
        document: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        mapping = cls._document_to_mapping(document)
        return mapping.get(field_name, default)

    def _clear_index(self) -> None:
        self._documents = []
        self._tokenised_corpus = []
        self._index = None

    def build_index(
        self,
        documents: list[Any] | None = None,
    ) -> None:
        if documents is None:
            source_documents = self.repository.list_all()
        else:
            source_documents = documents

        if not source_documents:
            self._clear_index()

            raise ValueError(
                "Cannot build the BM25 index because no documents were "
                "supplied."
            )

        usable_documents: list[Any] = []
        tokenised_corpus: list[list[str]] = []

        for document in source_documents:
            searchable_text = self._get_value(
                document,
                "searchable_text",
                "",
            )

            if not isinstance(searchable_text, str):
                searchable_text = str(searchable_text or "")

            if not searchable_text.strip():
                continue

            tokens = self.processor.preprocess(searchable_text)

            if not tokens:
                continue

            usable_documents.append(document)
            tokenised_corpus.append(tokens)

        if not usable_documents:
            self._clear_index()

            raise ValueError(
                "Search documents exist, but none contain searchable text."
            )

        self._documents = usable_documents
        self._tokenised_corpus = tokenised_corpus
        self._index = BM25Okapi(tokenised_corpus)

    def _build_result(
        self,
        document: Any,
        score: float,
        matched_terms: list[str],
        rank: int,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "rank": rank,
            "bm25_score": round(score, 6),
            "matched_terms": matched_terms,
        }

        for field_name in self._RESULT_FIELDS:
            result[field_name] = self._get_value(document, field_name)

        fts_score = self._get_value(document, "fts_score")

        if fts_score is not None:
            result["fts_score"] = fts_score

        return result

    def _collect_matched_terms(
        self,
        query_tokens: list[str],
        document_tokens: list[str],
    ) -> list[str]:
        document_token_set = set(document_tokens)
        matched: set[str] = set()

        for query_token in query_tokens:
            if query_token in document_token_set:
                matched.add(query_token)
                continue

            for document_token in document_tokens:
                if document_token.startswith(f"{query_token}-"):
                    matched.add(query_token)
                    break

                if document_token.startswith(f"{query_token}_"):
                    matched.add(query_token)
                    break

        return sorted(matched)

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not isinstance(query, str):
            raise TypeError("Search query must be a string.")

        if not query.strip():
            raise ValueError("Search query cannot be empty.")

        if not isinstance(top_k, int):
            raise TypeError("top_k must be an integer.")

        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        if not self.index_ready or self._index is None:
            raise RuntimeError(
                "BM25 index is not ready. Call build_index() first."
            )

        query_tokens = self.processor.preprocess(query)

        if not query_tokens:
            return []

        scores = self._index.get_scores(query_tokens)

        ranked_positions = sorted(
            range(len(scores)),
            key=lambda position: float(scores[position]),
            reverse=True,
        )

        results: list[dict[str, Any]] = []

        for position in ranked_positions:
            score = float(scores[position])

            document = self._documents[position]
            document_tokens = self._tokenised_corpus[position]

            matched_terms = self._collect_matched_terms(
                query_tokens,
                document_tokens,
            )

            if not matched_terms:
                continue

            results.append(
                self._build_result(
                    document=document,
                    score=score,
                    matched_terms=matched_terms,
                    rank=len(results) + 1,
                )
            )

            if len(results) >= top_k:
                break

        return results
