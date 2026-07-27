from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SearchDocument(BaseModel):
    drawing_id: str
    filename: str

    drawing_number: Optional[str] = None
    revision: Optional[str] = None
    title: Optional[str] = None
    material: Optional[str] = None

    part_numbers: str = ""
    dimensions_text: str = ""
    tolerances_text: str = ""
    notes_text: str = ""

    searchable_text: str

    analysis_version: str = "1.0"

    created_at: datetime
    updated_at: datetime