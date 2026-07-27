from datetime import datetime, timezone

from app.schemas import (
    Dimension,
    DrawingAnalysis,
    DrawingCallout,
    DatumReference,
    FeatureControlFrame,
)
from search.models.search_document import SearchDocument


class SearchDocumentBuilder:
    """Flattens a rich DrawingAnalysis into a SearchDocument."""

    @staticmethod
    def _join_parts(parts: list[str | None]) -> str:
        return " ".join(
            part.strip()
            for part in parts
            if part and part.strip()
        )

    @staticmethod
    def _format_dimension(dimension: Dimension) -> str:
        parts = [dimension.value]

        if dimension.tolerance:
            parts.append(dimension.tolerance)

        if dimension.dimension_type:
            parts.append(dimension.dimension_type)

        if dimension.reference:
            parts.append(dimension.reference)

        if dimension.view:
            parts.append(dimension.view)

        return " ".join(parts)

    @staticmethod
    def _format_feature_control_frame(frame: FeatureControlFrame) -> str:
        if frame.raw_text:
            return frame.raw_text.strip()

        parts: list[str] = []

        if frame.characteristic:
            parts.append(frame.characteristic)

        if frame.tolerance:
            parts.append(frame.tolerance)

        if frame.datums:
            parts.extend(frame.datums)

        return " ".join(parts)

    @staticmethod
    def _format_callout(callout: DrawingCallout) -> str:
        if callout.text:
            return f"{callout.identifier} {callout.text}".strip()

        return callout.identifier

    @staticmethod
    def _format_datum(datum: DatumReference) -> str:
        if datum.description:
            return f"{datum.label} {datum.description}".strip()

        return datum.label

    def build(
        self,
        drawing_id: str,
        filename: str,
        analysis: DrawingAnalysis,
    ) -> SearchDocument:
        now = datetime.now(timezone.utc)
        metadata = analysis.metadata

        dimensions_text = self._join_parts(
            [self._format_dimension(dimension) for dimension in analysis.dimensions]
        )

        tolerances_text = self._join_parts(
            list(analysis.general_tolerances)
            + [
                self._format_feature_control_frame(frame)
                for frame in analysis.feature_control_frames
            ]
        )

        notes_text = self._join_parts(
            list(analysis.manufacturing_notes)
            + list(analysis.inspection_notes)
        )

        part_numbers = self._join_parts(
            [self._format_callout(callout) for callout in analysis.callouts]
        )

        datums_text = self._join_parts(
            [self._format_datum(datum) for datum in analysis.datums]
        )

        symbols_text = self._join_parts(analysis.detected_symbols)

        searchable_text = self._join_parts(
            [
                filename,
                metadata.drawing_number,
                metadata.revision,
                metadata.title,
                metadata.material,
                metadata.finish,
                metadata.units,
                part_numbers,
                dimensions_text,
                tolerances_text,
                notes_text,
                datums_text,
                symbols_text,
                analysis.component_description,
                analysis.summary,
                self._join_parts(analysis.ambiguities),
                self._join_parts(analysis.unreadable_regions),
            ]
        )

        if not searchable_text:
            raise ValueError(
                "Cannot build a search document from an empty analysis."
            )

        return SearchDocument(
            drawing_id=drawing_id,
            filename=filename,
            drawing_number=metadata.drawing_number,
            revision=metadata.revision,
            title=metadata.title,
            material=metadata.material,
            finish=metadata.finish,
            units=metadata.units,
            part_numbers=part_numbers,
            dimensions_text=dimensions_text,
            tolerances_text=tolerances_text,
            notes_text=notes_text,
            searchable_text=searchable_text,
            analysis_version="1.0",
            created_at=now,
            updated_at=now,
        )
