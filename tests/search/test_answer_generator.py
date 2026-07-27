from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import openai
import pytest
from unittest.mock import patch

from search.services.answer_generator import DrawingAnswerGenerator


class _FakeCompletions:
    def __init__(self, response_text: str = "Grounded answer.") -> None:
        self.response_text = response_text
        self.last_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs

        if self.response_text == "__raise_auth__":
            raise openai.AuthenticationError(
                "Authentication failed",
                response=MagicMock(),
                body=None,
            )

        message = SimpleNamespace(content=self.response_text)
        choice = SimpleNamespace(message=message)

        return SimpleNamespace(choices=[choice])


class _FakeChat:
    def __init__(self, response_text: str = "Grounded answer.") -> None:
        self.completions = _FakeCompletions(response_text)


class _FakeClient:
    def __init__(self, response_text: str = "Grounded answer.") -> None:
        self.chat = _FakeChat(response_text)


def test_uses_injected_fake_client() -> None:
    client = _FakeClient("Aluminium 6061-T6 is specified.")
    generator = DrawingAnswerGenerator(
        client=client,
        model="test-model",
    )

    answer = generator.generate("Prompt text")

    assert answer == "Aluminium 6061-T6 is specified."
    assert client.chat.completions.last_kwargs is not None
    assert client.chat.completions.last_kwargs["model"] == "test-model"
    assert client.chat.completions.last_kwargs["temperature"] == 0.0
    assert client.chat.completions.last_kwargs["max_tokens"] == 1200


def test_blank_prompt_rejected() -> None:
    generator = DrawingAnswerGenerator(
        client=_FakeClient(),
        model="test-model",
    )

    with pytest.raises(ValueError, match="blank"):
        generator.generate("   ")


def test_empty_model_response_raises_runtime_error() -> None:
    generator = DrawingAnswerGenerator(
        client=_FakeClient(""),
        model="test-model",
    )

    with pytest.raises(RuntimeError, match="empty response"):
        generator.generate("Valid prompt")


def test_api_exception_becomes_runtime_error() -> None:
    generator = DrawingAnswerGenerator(
        client=_FakeClient("__raise_auth__"),
        model="test-model",
    )

    with pytest.raises(RuntimeError, match="authentication failed"):
        generator.generate("Valid prompt")


def test_secrets_not_included_in_exceptions() -> None:
    generator = DrawingAnswerGenerator(
        client=_FakeClient("__raise_auth__"),
        model="test-model",
    )

    secret = "sk-test-secret-value-12345"

    try:
        generator.generate(f"Prompt mentioning {secret}")
    except RuntimeError as exc:
        assert secret not in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_injected_client_without_model_raises_value_error() -> None:
    with patch(
        "search.services.answer_generator.OPENAI_ANSWER_MODEL",
        None,
    ):
        with pytest.raises(ValueError, match="model must not be blank"):
            DrawingAnswerGenerator(client=_FakeClient(), model=None)


def test_injected_client_with_explicit_model_works() -> None:
    generator = DrawingAnswerGenerator(
        client=_FakeClient("Grounded answer."),
        model="test-model",
    )

    assert generator.generate("Valid prompt") == "Grounded answer."
