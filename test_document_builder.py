from search.services.search_document_builder import SearchDocumentBuilder


analysis = {
    "drawing_number": "DR-1023",
    "revision": "C",
    "title": "Mounting Bracket",
    "material": "Aluminium 6061-T6",
    "part_numbers": ["PN-1001", "PN-1002"],
    "dimensions": [
        "Length 120 mm",
        "Width 80 mm",
        "Hole diameter 10 mm",
    ],
    "tolerances": {
        "general": "plus or minus 0.05 mm"
    },
    "notes": [
        "Surface finish anodised",
        "Deburr all edges",
    ],
    "analysis_version": "1.0",
}

builder = SearchDocumentBuilder()

document = builder.build(
    drawing_id="drawing-001",
    filename="mounting_bracket.pdf",
    analysis=analysis,
)

assert document.drawing_id == "drawing-001"
assert document.drawing_number == "DR-1023"
assert document.revision == "C"
assert document.material == "Aluminium 6061-T6"

assert "PN-1001" in document.part_numbers
assert "120 mm" in document.dimensions_text
assert "0.05 mm" in document.tolerances_text
assert "anodised" in document.notes_text
assert "Mounting Bracket" in document.searchable_text

print("Search document builder test passed successfully!")
print()
print("Generated searchable text:")
print(document.searchable_text)
