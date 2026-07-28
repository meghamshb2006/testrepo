from __future__ import annotations

from search.services.query_preprocessor import EngineeringQueryPreprocessor


def test_preprocesses_revision() -> None:
    preprocessor = EngineeringQueryPreprocessor()
    result = preprocessor.preprocess("show revision C drawings")

    assert any(
        item.identifier_type == "revision" and item.value == "REV C"
        for item in result.identifiers
    )
    assert "REV C" in result.normalized_query


def test_preprocesses_material_hyphenation() -> None:
    preprocessor = EngineeringQueryPreprocessor()
    result = preprocessor.preprocess("material 6061-t6 bracket")

    assert any(
        item.identifier_type == "material" and item.value == "6061-T6"
        for item in result.identifiers
    )
    assert "6061-T6" in result.normalized_query


def test_preprocesses_standard() -> None:
    preprocessor = EngineeringQueryPreprocessor()
    result = preprocessor.preprocess("tolerance iso 2768")

    assert any(
        item.identifier_type == "standard" and item.value == "ISO-2768"
        for item in result.identifiers
    )
    assert '"ISO-2768"' in result.fts_query
