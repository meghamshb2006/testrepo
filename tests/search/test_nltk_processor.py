from __future__ import annotations

import pytest

from search.services.nltk_processor import NLTKProcessor


@pytest.fixture
def processor() -> NLTKProcessor:
    return NLTKProcessor()


def test_preserves_engineering_identifiers(processor: NLTKProcessor) -> None:
    text = (
        "Find drawings for Aluminium 6061-T6 mounting bracket "
        "with ISO-2768 tolerance and part BR-1001."
    )

    tokens = processor.preprocess(text)

    assert "6061-t6" in tokens
    assert "iso-2768" in tokens
    assert "br-1001" in tokens
    assert "aluminium" in tokens
    assert "find" not in tokens
    assert "with" not in tokens


def test_preserves_decimal_dimensions(processor: NLTKProcessor) -> None:
    text = "Hole diameter 10.5 mm with tolerance plusminus 0.05 mm."

    tokens = processor.preprocess(text)

    assert "10.5" in tokens
    assert "0.05" in tokens
    assert "plusminus" in tokens
    assert "mm" in tokens
