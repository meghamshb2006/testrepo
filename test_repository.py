from datetime import datetime, timezone
from pathlib import Path

from search.database import SearchDatabase
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository


TEST_DATABASE = Path("data/test_drawing_search.db")

if TEST_DATABASE.exists():
    TEST_DATABASE.unlink()


db = SearchDatabase(str(TEST_DATABASE))
db.initialize()

repository = SearchRepository(db)

now = datetime.now(timezone.utc)

document = SearchDocument(
    drawing_id="drawing-001",
    filename="mounting_bracket.pdf",
    drawing_number="DR-1023",
    revision="C",
    title="Mounting Bracket",
    material="Aluminium 6061-T6",
    part_numbers="PN-1001",
    dimensions_text="120 mm 80 mm hole diameter 10 mm",
    tolerances_text="plus or minus 0.05 mm",
    notes_text="Surface finish anodised. Deburr all edges.",
    searchable_text=(
        "DR-1023 mounting bracket aluminium 6061-T6 "
        "PN-1001 120 mm 80 mm hole diameter 10 mm "
        "tolerance plus or minus 0.05 mm "
        "surface finish anodised deburr all edges revision C"
    ),
    analysis_version="1.0",
    created_at=now,
    updated_at=now,
)

repository.upsert(document)

stored = repository.get_by_drawing_id("drawing-001")
assert stored is not None
assert stored["filename"] == "mounting_bracket.pdf"
assert stored["material"] == "Aluminium 6061-T6"

assert repository.count() == 1

results = repository.search_fts("aluminium AND bracket")
assert len(results) == 1
assert results[0]["drawing_id"] == "drawing-001"

all_documents = repository.list_all()
assert len(all_documents) == 1

deleted = repository.delete("drawing-001")
assert deleted is True
assert repository.count() == 0

db.close()

if TEST_DATABASE.exists():
    TEST_DATABASE.unlink()

print("Repository test passed successfully!")
