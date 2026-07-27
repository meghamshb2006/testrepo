from search.services.nltk_processor import NLTKProcessor


processor = NLTKProcessor()

text = (
    "Find drawings for an Aluminium 6061-T6 mounting bracket "
    "with diameter 10.5 mm holes and tolerance plusminus 0.05 mm."
)

tokens = processor.preprocess(text)

print("Processed tokens:")
print(tokens)

assert "aluminium" in tokens
assert "6061-t6" in tokens
assert "diameter" in tokens
assert "10.5" in tokens
assert "mm" in tokens
assert "plusminus" in tokens
assert "0.05" in tokens
assert "find" not in tokens
assert "with" not in tokens

print()
print("NLTK processor test passed successfully!")