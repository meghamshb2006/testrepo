from search.engines.bm25_engine import BM25SearchEngine


engine = BM25SearchEngine()

engine.build_index()

results = engine.search(
    "aluminium housing"
)

print(results)

print("Search engine test passed!")
