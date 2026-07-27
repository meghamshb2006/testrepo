from pydantic import BaseModel, Field


class DrawingMetadata(BaseModel):
    drawing_number: str | None = None
    title: str | None = None
    revision: str | None = None
    date: str | None = None
    scale: str | None = None
    sheet_number: str | None = None
    total_sheets: str | None = None
    material: str | None = None
    finish: str | None = None
    units: str | None = None


class Dimension(BaseModel):
    value: str
    dimension_type: str | None = None
    tolerance: str | None = None
    reference: str | None = None
    view: str | None = None


class FeatureControlFrame(BaseModel):
    characteristic: str | None = None
    tolerance: str | None = None
    datums: list[str] = Field(default_factory=list)
    raw_text: str | None = None


class DatumReference(BaseModel):
    label: str
    description: str | None = None
    view: str | None = None


class DrawingView(BaseModel):
    name: str
    view_type: str | None = None
    description: str | None = None


class DrawingCallout(BaseModel):
    identifier: str
    text: str | None = None
    view: str | None = None


class DrawingAnalysis(BaseModel):
    metadata: DrawingMetadata = Field(default_factory=DrawingMetadata)

    views: list[DrawingView] = Field(default_factory=list)
    dimensions: list[Dimension] = Field(default_factory=list)
    feature_control_frames: list[FeatureControlFrame] = Field(
        default_factory=list
    )
    datums: list[DatumReference] = Field(default_factory=list)
    callouts: list[DrawingCallout] = Field(default_factory=list)

    general_tolerances: list[str] = Field(default_factory=list)
    manufacturing_notes: list[str] = Field(default_factory=list)
    inspection_notes: list[str] = Field(default_factory=list)
    detected_symbols: list[str] = Field(default_factory=list)

    component_description: str | None = None
    summary: str | None = None
    ambiguities: list[str] = Field(default_factory=list)
    unreadable_regions: list[str] = Field(default_factory=list)


class DrawingAnalysisResponse(BaseModel):
    document_id: str
    status: str
    analysis: DrawingAnalysis