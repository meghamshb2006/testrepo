from __future__ import annotations

import openai
from openai import OpenAI

from app.config import (
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL,
)


class EmbeddingService:
    def __init__(self) -> None:
        self._validate_configuration()

        self.client = OpenAI(
            api_key=EMBEDDING_API_KEY,
            base_url=EMBEDDING_BASE_URL,
            timeout=120.0,
            max_retries=2,
        )

        self.model = EMBEDDING_MODEL

    @staticmethod
    def _validate_configuration() -> None:
        missing: list[str] = []

        if not EMBEDDING_API_KEY:
            missing.append("EMBEDDING_API_KEY")

        if not EMBEDDING_BASE_URL:
            missing.append("EMBEDDING_BASE_URL")

        if not EMBEDDING_MODEL:
            missing.append("EMBEDDING_MODEL")

        if missing:
            raise RuntimeError(
                "Embedding configuration is incomplete. Missing: "
                + ", ".join(missing)
            )

    def generate_embedding(
        self,
        text: str,
    ) -> list[float]:
        cleaned_text = text.strip()

        if not cleaned_text:
            raise ValueError(
                "Cannot generate an embedding for empty text."
            )

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=cleaned_text,
                encoding_format="float",
            )

        except openai.AuthenticationError as exc:
            raise RuntimeError(
                "Embedding API authentication failed."
            ) from exc

        except openai.PermissionDeniedError as exc:
            raise RuntimeError(
                f"The API key cannot access embedding model "
                f"'{self.model}'."
            ) from exc

        except openai.NotFoundError as exc:
            raise RuntimeError(
                f"Embedding model or deployment "
                f"'{self.model}' was not found."
            ) from exc

        except openai.RateLimitError as exc:
            raise RuntimeError(
                "Embedding API rate limit or quota was exceeded."
            ) from exc

        except openai.APIConnectionError as exc:
            raise RuntimeError(
                "Could not connect to the embedding endpoint."
            ) from exc

        except openai.APIStatusError as exc:
            raise RuntimeError(
                f"Embedding request failed with status "
                f"{exc.status_code}: {exc}"
            ) from exc

        if not response.data:
            raise RuntimeError(
                "The embedding endpoint returned no vectors."
            )

        embedding = response.data[0].embedding

        if not embedding:
            raise RuntimeError(
                "The embedding endpoint returned an empty vector."
            )

        return [float(value) for value in embedding]

    def generate_embeddings(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        cleaned_texts = [
            text.strip()
            for text in texts
            if text.strip()
        ]

        if not cleaned_texts:
            raise ValueError(
                "No non-empty text was supplied for embedding."
            )

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=cleaned_texts,
                encoding_format="float",
            )

        except openai.APIError as exc:
            raise RuntimeError(
                f"Batch embedding request failed: {exc}"
            ) from exc

        ordered = sorted(
            response.data,
            key=lambda item: item.index,
        )

        embeddings = [
            [float(value) for value in item.embedding]
            for item in ordered
        ]

        if len(embeddings) != len(cleaned_texts):
            raise RuntimeError(
                "The embedding endpoint returned an unexpected "
                "number of vectors."
            )

        return embeddings
