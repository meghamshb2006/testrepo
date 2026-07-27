from pathlib import Path

from search.database import SearchDatabase
from search.engines.bm25_engine import BM25SearchEngine
from search.repositories.search_repository import SearchRepository
from search.services.nltk_processor import NLTKProcessor
from search.services.search_document_builder import SearchDocumentBuilder


DATABASE_PATH = Path("data") / "test_bm25_search.db"

if DATABASE_PATH.exists():
    DATABASE_PATH.unlink()


database = SearchDatabase(str(DATABASE_PATH))

try:
    database.initialize()

    repository = SearchRepository(database)
    builder = SearchDocumentBuilder()

    test_drawings = [
        {
            "drawing_id": "drawing-001",
            "filename": "aluminium_mounting_bracket.pdf",
            "analysis": {
                "drawing_number": "DR-1001",
                "revision": "C",
                "title": "Aluminium Mounting Bracket",
                "material": "Aluminium 6061-T6",
                "part_numbers": ["BR-1001"],
                "dimensions": [
                    "Length 120 mm",
                    "Width 80 mm",
                    "Hole diameter 10.5 mm",
                ],
                "tolerances": [
                    "General tolerance plusminus 0.05 mm",
                ],
                "notes": [
                    "Surface finish anodized",
                    "Deburr all edges",
                ],
            },
        },
        {
            "drawing_id": "drawing-002",
            "filename": "stainless_motor_housing.pdf",
            "analysis": {
                "drawing_number": "DR-2002",
                "revision": "B",
                "title": "Stainless Steel Motor Housing",
                "material": "Stainless Steel 316",
                "part_numbers": ["MH-2002"],
                "dimensions": [
                    "Outer diameter 150 mm",
                    "Inner diameter 120 mm",
                ],
                "tolerances": [
                    "General tolerance plusminus 0.10 mm",
                ],
                "notes": [
                    "Machine all critical surfaces",
                    "Remove sharp edges",
                ],
            },
        },
        {
            "drawing_id": "drawing-003",
            "filename": "copper_busbar.pdf",
            "analysis": {
                "drawing_number": "DR-3003",
                "revision": "A",
                "title": "Electrical Copper Busbar",
                "material": "Copper C110",
                "part_numbers": ["CB-3003"],
                "dimensions": [
                    "Length 300 mm",
                    "Width 30 mm",
                    "Thickness 5 mm",
                ],
                "tolerances": [
                    "General tolerance plusminus 0.20 mm",
                ],
                "notes": [
                    "Tin plated surface",
                    "Electrical contact component",
                ],
            },
        },
    ]

    for item in test_drawings:
        document = builder.build(
            drawing_id=item["drawing_id"],
            filename=item["filename"],
            analysis=item["analysis"],
        )
        repository.upsert(document)

    print(f"Documents stored in SQLite: {repository.count()}")

    engine = BM25SearchEngine(
        repository=repository,
        processor=NLTKProcessor(),
    )

    engine.build_index()

    print("BM25 index built successfully")
    print()

    results = engine.search(
        query="aluminium 6061-T6 bracket with 10.5 mm hole",
        top_k=3,
    )

    print("BM25 search results:")
    print()

    for result in results:
        print(
            f'{result["rank"]}. '
            f'{result["filename"]} | '
            f'score={result["bm25_score"]} | '
            f'matched={result["matched_terms"]}'
        )

    assert results[0]["drawing_id"] == "drawing-001"

    print()
    print("Real SQLite and BM25 integration test passed successfully!")

finally:
    database.close()

    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
