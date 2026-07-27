from abc import ABC, abstractmethod
from typing import Any


class SearchEngine(ABC):
    """
    Abstract interface for all search engines.
    """

    @abstractmethod
    def build_index(
        self,
        documents: list[Any] | None = None,
    ) -> None:
        """
        Build or rebuild the search index.
        """
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[Any]:
        """
        Search for the most relevant documents.
        """
        raise NotImplementedError
