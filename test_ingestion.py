from pathlib import Path

from search.database import SearchDatabase
from search.repositories.search_repository import SearchRepository
from search.services.search_document_builder import SearchDocumentBuilder


TEST_DATABASE = Path("data/test_ingestion.db")

if TEST_DATABASE.exists():
    TEST_DATABASE.unlink()


analysis = {
    "drawing_number": "DR-2048",
    "revision": "B",
    "title": "Motor Housing",
    "material": "Stainless Steel 316",
    "part_numbers": ["MH-2048"],
    "dimensions": [
        "Outer diameter 150 mm",
        "Inner diameter 120 mm",
    ],
    "tolerances": ["plus or minus 0.1 mm"],
    "notes": [
        "Machine all critical surfaces",
        "Remove sharp edges",
    ],
}


database = SearchDatabase(str(TEST_DATABASE))
database.initialize()

repository = SearchRepository(database)
builder = SearchDocumentBuilder()

document = builder.build(
    drawing_id="drawing-002",
    filename="motor_housing.pdf",
    analysis=analysis,
)

repository.upsert(document)

stored = repository.get_by_drawing_id("drawing-002")

assert stored is not None
assert stored["drawing_number"] == "DR-2048"
assert stored["material"] == "Stainless Steel 316"

results = repository.search_fts("stainless AND housing")

assert len(results) == 1
assert results[0]["drawing_id"] == "drawing-002"

database.close()

if TEST_DATABASE.exists():
    TEST_DATABASE.unlink()

print("Complete ingestion test passed successfully!")
