from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DrawingAnalysis(BaseModel):
    """
    Validated structured information extracted from an engineering drawing.
    """

    model_config = ConfigDict(
        extra="allow",
        str_strip_whitespace=True,
    )

    drawing_number: str | None = None
    revision: str | None = None
    title: str | None = None
    material: str | None = None

    part_numbers: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    tolerances: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    page_number: int | None = Field(default=None, ge=1)
    page_analyses: list[dict[str, Any]] = Field(default_factory=list)

    analysis_version: str = "1.0"

    @field_validator(
        "part_numbers",
        "dimensions",
        "tolerances",
        "notes",
        mode="before",
    )
    @classmethod
    def normalise_list_field(cls, value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            stripped = value.strip()
            return [stripped] if stripped else []

        if isinstance(value, (tuple, set)):
            value = list(value)

        if not isinstance(value, list):
            value = [value]

        normalised: list[str] = []

        for item in value:
            if item is None:
                continue

            if isinstance(item, dict):
                text = " ".join(
                    f"{key.replace('_', ' ')} {item_value}"
                    for key, item_value in item.items()
                    if item_value is not None
                ).strip()
            else:
                text = str(item).strip()

            if text:
                normalised.append(text)

        return normalised
