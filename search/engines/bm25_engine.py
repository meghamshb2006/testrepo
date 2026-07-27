from __future__ import annotations

from typing import Any, Mapping

from rank_bm25 import BM25Okapi

from search.engines.search_engine import SearchEngine
from search.repositories.search_repository import SearchRepository
from search.services.nltk_processor import NLTKProcessor


class BM25SearchEngine(SearchEngine):
    """
    Real BM25 search engine backed by SearchRepository documents.

    The index is built from searchable_text stored in SQLite.
    Search results contain real BM25 scores and matched query terms.
    """

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

    def build_index(self) -> None:
        repository_documents = self.repository.list_all()

        if not repository_documents:
            self._documents = []
            self._tokenised_corpus = []
            self._index = None

            raise ValueError(
                "Cannot build the BM25 index because SQLite contains "
                "no search documents."
            )

        usable_documents: list[Any] = []
        tokenised_corpus: list[list[str]] = []

        for document in repository_documents:
            searchable_text = self._get_value(
                document,
                "searchable_text",
                "",
            )

            if not isinstance(searchable_text, str):
                searchable_text = str(searchable_text or "")

            tokens = self.processor.preprocess(searchable_text)

            if not tokens:
                continue

            usable_documents.append(document)
            tokenised_corpus.append(tokens)

        if not usable_documents:
            self._documents = []
            self._tokenised_corpus = []
            self._index = None

            raise ValueError(
                "Search documents exist, but none contain searchable text."
            )

        self._documents = usable_documents
        self._tokenised_corpus = tokenised_corpus
        self._index = BM25Okapi(tokenised_corpus)

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

            if score <= 0:
                continue

            document = self._documents[position]
            document_tokens = self._tokenised_corpus[position]

            matched_terms = sorted(
                set(query_tokens).intersection(document_tokens)
            )

            result = {
                "rank": len(results) + 1,
                "drawing_id": self._get_value(
                    document,
                    "drawing_id",
                ),
                "filename": self._get_value(
                    document,
                    "filename",
                ),
                "drawing_number": self._get_value(
                    document,
                    "drawing_number",
                ),
                "revision": self._get_value(
                    document,
                    "revision",
                ),
                "title": self._get_value(
                    document,
                    "title",
                ),
                "material": self._get_value(
                    document,
                    "material",
                ),
                "part_numbers": self._get_value(
                    document,
                    "part_numbers",
                    [],
                ),
                "bm25_score": round(score, 6),
                "matched_terms": matched_terms,
                "searchable_text": self._get_value(
                    document,
                    "searchable_text",
                    "",
                ),
            }

            results.append(result)

            if len(results) >= top_k:
                break

        return results
