from __future__ import annotations

import re
from datetime import datetime, timezone

from app.schemas import (
    Dimension,
    DrawingAnalysis,
    DrawingCallout,
    DatumReference,
    FeatureControlFrame,
)
from search.models.search_document import SearchDocument


_IDENTIFIER_PATTERN = re.compile(
    r"(?:"
    r"[A-Za-z]{1,6}-\d+[A-Za-z0-9-]*"
    r"|ISO[-\s]?\d+[A-Za-z0-9-]*"
    r"|DIN[-\s]?\d+[A-Za-z0-9-]*"
    r"|ASTM[-\s]?[A-Za-z0-9-]+"
    r"|\d{3,5}-[Tt]\d+"
    r"|M\d+(?:x[\d.]+)?"
    r"|REV\s*[A-Za-z0-9]+"
    r"|[+-]/?\d+(?:\.\d+)?"
    r")"
)

_STANDARD_PATTERN = re.compile(
    r"\b(?:ISO|DIN|ANSI|ASTM)[-\s]?\d+[A-Za-z0-9-]*\b",
    re.IGNORECASE,
)


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
    def _dedupe_join(parts: list[str | None]) -> str:
        seen: set[str] = set()
        unique: list[str] = []

        for part in parts:
            if not part or not part.strip():
                continue

            cleaned = part.strip()
            key = re.sub(r"\s+", " ", cleaned).casefold()

            if key in seen:
                continue

            seen.add(key)
            unique.append(cleaned)

        return " ".join(unique)

    @classmethod
    def _clean_free_text(cls, text: str | None) -> str:
        if not text:
            return ""

        placeholders: dict[str, str] = {}

        def _preserve(match: re.Match[str]) -> str:
            key = f"__ID{len(placeholders)}__"
            placeholders[key] = match.group(0)
            return key

        protected = _IDENTIFIER_PATTERN.sub(_preserve, text)
        cleaned = re.sub(r"\s+", " ", protected)
        cleaned = re.sub(r"([^\w\s])\1+", r"\1", cleaned)
        cleaned = cleaned.strip()

        for key, value in placeholders.items():
            cleaned = cleaned.replace(key, value)

        return cleaned

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

    @classmethod
    def _extract_standards(cls, analysis: DrawingAnalysis) -> str:
        candidates: list[str] = []

        for value in analysis.general_tolerances:
            candidates.append(value)

        for value in analysis.manufacturing_notes:
            candidates.append(value)

        for value in analysis.inspection_notes:
            candidates.append(value)

        found: list[str] = []
        seen: set[str] = set()

        for text in candidates:
            for match in _STANDARD_PATTERN.finditer(text):
                raw = re.sub(r"\s+", "-", match.group(0).upper())
                prefix_match = re.match(
                    r"^(ISO|DIN|ANSI|ASTM)-?(.*)$",
                    raw,
                )

                if not prefix_match:
                    continue

                prefix, remainder = prefix_match.groups()
                standard = f"{prefix}-{remainder.lstrip('-')}"
                key = standard.casefold()

                if key in seen:
                    continue

                seen.add(key)
                found.append(standard)

        return " ".join(found)

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

        notes_text = self._clean_free_text(
            self._join_parts(
                list(analysis.manufacturing_notes)
                + list(analysis.inspection_notes)
            )
        )

        part_numbers = self._join_parts(
            [self._format_callout(callout) for callout in analysis.callouts]
        )

        primary_part = None

        if analysis.callouts:
            primary_part = analysis.callouts[0].identifier

        datums_text = self._join_parts(
            [self._format_datum(datum) for datum in analysis.datums]
        )

        symbols_text = self._join_parts(analysis.detected_symbols)
        engineering_standards = self._extract_standards(analysis)

        components = self._clean_free_text(
            self._join_parts(
                [
                    analysis.component_description,
                    part_numbers,
                ]
            )
        )

        referenced_parts = part_numbers
        manufacturing_process = self._clean_free_text(
            self._join_parts(list(analysis.manufacturing_notes))
        )
        engineering_notes = notes_text
        body = self._clean_free_text(
            self._join_parts(
                [
                    analysis.summary,
                    analysis.component_description,
                    self._join_parts(analysis.ambiguities),
                ]
            )
        )

        searchable_text = self._dedupe_join(
            [
                filename,
                metadata.drawing_number,
                metadata.revision,
                metadata.title,
                metadata.material,
                metadata.finish,
                metadata.units,
                metadata.sheet_number,
                metadata.scale,
                part_numbers,
                dimensions_text,
                tolerances_text,
                notes_text,
                manufacturing_process,
                engineering_standards,
                analysis.component_description,
                analysis.summary,
                self._join_parts(analysis.ambiguities),
                datums_text,
                symbols_text,
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
            sheet_number=metadata.sheet_number,
            scale=metadata.scale,
            part_number=primary_part,
            part_numbers=part_numbers,
            dimensions_text=dimensions_text,
            tolerances_text=tolerances_text,
            notes_text=notes_text,
            manufacturing_process=manufacturing_process,
            engineering_standards=engineering_standards,
            referenced_parts=referenced_parts,
            components=components,
            engineering_notes=engineering_notes,
            body=body,
            searchable_text=searchable_text,
            analysis_version="1.1",
            created_at=now,
            updated_at=now,
        )
