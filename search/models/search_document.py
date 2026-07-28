from datetime import datetime

from pydantic import BaseModel


class SearchDocument(BaseModel):
    drawing_id: str
    filename: str

    drawing_number: str | None = None
    revision: str | None = None
    title: str | None = None
    material: str | None = None
    finish: str | None = None
    units: str | None = None

    sheet_number: str | None = None
    scale: str | None = None
    part_number: str | None = None

    part_numbers: str = ""
    dimensions_text: str = ""
    tolerances_text: str = ""
    notes_text: str = ""

    manufacturing_process: str = ""
    engineering_standards: str = ""
    referenced_parts: str = ""
    components: str = ""
    engineering_notes: str = ""
    body: str = ""

    searchable_text: str

    analysis_version: str = "1.1"

    created_at: datetime
    updated_at: datetime
