from __future__ import annotations

from search.context.context_builder import ContextBuilder


def test_truncates_first_section_when_it_exceeds_limit() -> None:
    results = [
        {
            "drawing_id": "drawing-001",
            "filename": "mounting_bracket.pdf",
            "drawing_number": "DR-1023",
            "revision": "C",
            "title": "Mounting Bracket",
            "material": "Aluminium 6061-T6",
            "finish": "Anodised",
            "units": "mm",
            "part_numbers": "BR-1001",
            "dimensions_text": "120 mm hole diameter 10 mm",
            "tolerances_text": "ISO-2768-mK plusminus 0.05 mm",
            "notes_text": "Surface finish anodised. Deburr all edges.",
            "bm25_score": 1.5,
            "searchable_text": "DR-1023 mounting bracket aluminium 6061-T6",
        }
    ]

    context = ContextBuilder.build_context(
        results,
        max_documents=1,
        max_characters=250,
    )

    assert context
    assert len(context) <= 250
    assert "[context truncated]" in context
    assert "Retrieved Drawing 1" in context
    assert "DR-1023" in context


def test_includes_multiple_sections_when_space_allows() -> None:
    results = [
        {
            "drawing_id": "drawing-001",
            "filename": "a.pdf",
            "drawing_number": "DR-1",
            "title": "Part A",
            "material": "Aluminium",
            "bm25_score": 1.0,
        },
        {
            "drawing_id": "drawing-002",
            "filename": "b.pdf",
            "drawing_number": "DR-2",
            "title": "Part B",
            "material": "Steel",
            "bm25_score": 0.5,
        },
    ]

    context = ContextBuilder.build_context(
        results,
        max_documents=2,
        max_characters=2000,
    )

    assert "Retrieved Drawing 1" in context
    assert "Retrieved Drawing 2" in context


def test_dedupes_identical_field_values_and_prefers_exact_match() -> None:
    results = [
        {
            "drawing_id": "drawing-002",
            "filename": "other.pdf",
            "drawing_number": "DR-2",
            "title": "Other",
            "notes_text": "Deburr edges",
            "engineering_notes": "Deburr edges",
            "bm25_score": 2.0,
            "exact_identifier_match": False,
        },
        {
            "drawing_id": "drawing-001",
            "filename": "match.pdf",
            "drawing_number": "DR-1",
            "title": "Exact",
            "bm25_score": 1.0,
            "exact_identifier_match": True,
            "matched_identifiers": ["DR-1"],
        },
    ]

    context = ContextBuilder.build_context(
        results,
        max_documents=2,
        max_characters=4000,
    )

    assert context.index("drawing-001") < context.index("drawing-002")
    assert context.count("Deburr edges") == 1
    assert "Exact Identifier Match: yes" in context
