from __future__ import annotations

import logging
from typing import Any

import openai
from openai import OpenAI

from app.config import (
    OPENAI_ANSWER_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    validate_answer_config,
)

logger = logging.getLogger(__name__)


class DrawingAnswerGenerator:
    """Generates grounded answers using an OpenAI-compatible chat API."""

    def __init__(
        self,
        client: Any | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1200,
    ) -> None:
        if not isinstance(temperature, (int, float)):
            raise TypeError("temperature must be a number.")

        if temperature < 0 or temperature > 2:
            raise ValueError("temperature must be between 0 and 2.")

        if not isinstance(max_tokens, int):
            raise TypeError("max_tokens must be an integer.")

        if max_tokens < 1:
            raise ValueError("max_tokens must be at least 1.")

        self.temperature = float(temperature)
        self.max_tokens = max_tokens

        if client is None:
            validate_answer_config()
            self.client = OpenAI(
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL,
                timeout=300.0,
                max_retries=2,
            )
            self.model = model or OPENAI_ANSWER_MODEL
        else:
            self.client = client
            self.model = model or OPENAI_ANSWER_MODEL or "test-model"

        if not self.model or not str(self.model).strip():
            raise ValueError("model must not be blank.")

    def generate(self, prompt: str) -> str:
        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string.")

        if not prompt.strip():
            raise ValueError("prompt must not be blank.")

        logger.debug(
            "Generating answer with model=%s max_tokens=%s",
            self.model,
            self.max_tokens,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You answer questions about mechanical "
                            "engineering drawings using only supplied "
                            "retrieved context."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

        except openai.AuthenticationError as exc:
            raise RuntimeError(
                "API authentication failed. Check OPENAI_API_KEY."
            ) from exc

        except openai.PermissionDeniedError as exc:
            raise RuntimeError(
                f"The API key cannot access model '{self.model}'."
            ) from exc

        except openai.NotFoundError as exc:
            raise RuntimeError(
                f"Model or deployment '{self.model}' was not found."
            ) from exc

        except openai.RateLimitError as exc:
            raise RuntimeError(
                "API rate limit or account quota was exceeded."
            ) from exc

        except openai.APIConnectionError as exc:
            raise RuntimeError(
                "Could not connect to the configured AI endpoint."
            ) from exc

        except openai.APIStatusError as exc:
            raise RuntimeError(
                f"AI API request failed with status {exc.status_code}."
            ) from exc

        except openai.OpenAIError as exc:
            raise RuntimeError(
                "Answer generation request failed."
            ) from exc

        if not response.choices:
            raise RuntimeError("The model returned no response choices.")

        answer_text = response.choices[0].message.content

        if not answer_text or not answer_text.strip():
            raise RuntimeError("The model returned an empty response.")

        logger.debug("Answer generation completed.")

        return answer_text.strip()
