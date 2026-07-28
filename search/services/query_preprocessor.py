"""Deterministic engineering query normalization for lexical retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


IdentifierType = str

_REVISION_PATTERN = re.compile(
    r"\b(?:rev(?:ision)?)\s*[:#-]?\s*([A-Za-z0-9]+)\b",
    re.IGNORECASE,
)
_MATERIAL_PATTERN = re.compile(
    r"\b(\d{3,5})-([Tt]\d+)\b",
)
_STANDARD_PATTERN = re.compile(
    r"\b(ISO|DIN|ANSI|ASTM)\s*-?\s*(\d+[A-Za-z0-9-]*)\b",
    re.IGNORECASE,
)
_THREAD_PATTERN = re.compile(
    r"\b(M\d+(?:x[\d.]+)?)\b",
    re.IGNORECASE,
)
_DRAWING_OR_PART_PATTERN = re.compile(
    r"\b([A-Za-z]{1,6}-\d+[A-Za-z0-9-]*)\b",
)
_DIMENSION_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?\s*(?:mm|in|inch|inches)?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IdentifierMatch:
    value: str
    identifier_type: IdentifierType
    raw: str


@dataclass
class PreprocessedQuery:
    original_query: str
    normalized_query: str
    identifiers: list[IdentifierMatch] = field(default_factory=list)
    fts_query: str = ""
    residual_tokens: list[str] = field(default_factory=list)


class EngineeringQueryPreprocessor:
    """Normalize engineering queries and extract typed identifiers."""

    def preprocess(self, query: str) -> PreprocessedQuery:
        if not isinstance(query, str):
            raise TypeError("query must be a string.")

        if not query.strip():
            raise ValueError("query must not be blank.")

        original = query.strip()
        working = original
        identifiers: list[IdentifierMatch] = []
        seen: set[tuple[str, str]] = set()

        def _add(
            value: str,
            identifier_type: IdentifierType,
            raw: str,
        ) -> None:
            key = (identifier_type, value.casefold())

            if key in seen:
                return

            seen.add(key)
            identifiers.append(
                IdentifierMatch(
                    value=value,
                    identifier_type=identifier_type,
                    raw=raw,
                )
            )

        for match in _REVISION_PATTERN.finditer(working):
            code = match.group(1).upper()
            _add(f"REV {code}", "revision", match.group(0))
            working = working.replace(match.group(0), f" REV {code} ")

        for match in _MATERIAL_PATTERN.finditer(working):
            material = f"{match.group(1)}-{match.group(2).upper()}"
            _add(material, "material", match.group(0))
            working = working.replace(match.group(0), f" {material} ")

        for match in _STANDARD_PATTERN.finditer(working):
            standard = f"{match.group(1).upper()}-{match.group(2)}"
            _add(standard, "standard", match.group(0))
            working = working.replace(match.group(0), f" {standard} ")

        for match in _THREAD_PATTERN.finditer(working):
            thread = match.group(1).upper().replace("X", "x")
            _add(thread, "thread", match.group(0))
            working = working.replace(match.group(0), f" {thread} ")

        for match in _DRAWING_OR_PART_PATTERN.finditer(working):
            token = match.group(1).upper()
            identifier_type = (
                "drawing_number"
                if token.startswith(("DR-", "DWG-", "DW-"))
                else "part"
            )
            _add(token, identifier_type, match.group(0))
            working = working.replace(match.group(0), f" {token} ")

        for match in _DIMENSION_PATTERN.finditer(working):
            dim = re.sub(r"\s+", "", match.group(1).lower())
            if re.fullmatch(r"\d+(?:\.\d+)?", dim):
                continue
            _add(dim, "dimension", match.group(0))

        normalized = re.sub(r"\s+", " ", working).strip()
        identifier_values = {item.value for item in identifiers}
        residual_tokens: list[str] = []

        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9._+/-]*", normalized):
            if any(
                token.casefold() == value.casefold()
                or token.casefold() in value.casefold()
                for value in identifier_values
            ):
                continue

            if token.upper() in {"REV", "REVISION"}:
                continue

            residual_tokens.append(token.lower())

        fts_parts: list[str] = []

        for identifier in identifiers:
            quoted = f'"{identifier.value}"'
            if quoted not in fts_parts:
                fts_parts.append(quoted)

        for token in residual_tokens:
            if token not in fts_parts:
                fts_parts.append(token)

        if not fts_parts:
            fts_query = normalized
        elif len(fts_parts) == 1:
            fts_query = fts_parts[0]
        else:
            fts_query = " OR ".join(fts_parts)

        return PreprocessedQuery(
            original_query=original,
            normalized_query=normalized,
            identifiers=identifiers,
            fts_query=fts_query,
            residual_tokens=residual_tokens,
        )
