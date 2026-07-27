from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.schemas import (
    DatumReference,
    Dimension,
    DrawingAnalysis,
    DrawingCallout,
    DrawingMetadata,
    FeatureControlFrame,
)
from search.services.search_document_builder import SearchDocumentBuilder


@pytest.fixture
def builder() -> SearchDocumentBuilder:
    return SearchDocumentBuilder()


@pytest.fixture
def rich_analysis() -> DrawingAnalysis:
    return DrawingAnalysis(
        metadata=DrawingMetadata(
            drawing_number="DR-1023",
            revision="C",
            title="Mounting Bracket",
            material="Aluminium 6061-T6",
            finish="Anodised",
            units="mm",
        ),
        dimensions=[
            Dimension(
                value="120 mm",
                dimension_type="length",
                tolerance="plusminus 0.05 mm",
            ),
            Dimension(value="Hole diameter 10 mm"),
        ],
        feature_control_frames=[
            FeatureControlFrame(
                characteristic="flatness",
                tolerance="0.05",
                datums=["A", "B"],
                raw_text="flatness 0.05 | A | B",
            )
        ],
        datums=[
            DatumReference(label="A", description="Primary datum face"),
        ],
        callouts=[
            DrawingCallout(identifier="BR-1001", text="Mounting hole"),
        ],
        general_tolerances=["ISO-2768-mK"],
        manufacturing_notes=["Deburr all edges"],
        inspection_notes=["Inspect critical dimensions"],
        detected_symbols=["diameter", "GD&T"],
        component_description="Aluminium mounting bracket",
        summary="Bracket for motor assembly",
        ambiguities=["Revision stamp partially obscured"],
        unreadable_regions=["Lower-right title block corner"],
    )


def test_builds_search_document_from_rich_analysis(
    builder: SearchDocumentBuilder,
    rich_analysis: DrawingAnalysis,
) -> None:
    document = builder.build(
        drawing_id="drawing-001",
        filename="mounting_bracket.pdf",
        analysis=rich_analysis,
    )

    assert document.drawing_id == "drawing-001"
    assert document.drawing_number == "DR-1023"
    assert document.revision == "C"
    assert document.material == "Aluminium 6061-T6"
    assert document.finish == "Anodised"
    assert document.units == "mm"
    assert "BR-1001" in document.part_numbers
    assert "120 mm" in document.dimensions_text
    assert "ISO-2768-mK" in document.tolerances_text
    assert "flatness 0.05 | A | B" in document.tolerances_text
    assert "Deburr all edges" in document.notes_text
    assert "6061-T6" in document.searchable_text
    assert "ISO-2768-mK" in document.searchable_text
    assert "BR-1001" in document.searchable_text


def test_empty_analysis_raises(builder: SearchDocumentBuilder) -> None:
    empty_analysis = DrawingAnalysis()

    with pytest.raises(ValueError, match="empty analysis"):
        builder.build(
            drawing_id="drawing-empty",
            filename="",
            analysis=empty_analysis,
        )
