# Evaluation datasets

JSON benchmark suites and offline seed packs for retrieval validation.

| File | Purpose |
|------|---------|
| `sample_benchmark.json` | Generic Milestone 6 template |
| `retrieval_intelligence_suites.json` | Milestone 7.1 confidence/category suite |
| `golden_seed_documents.json` | Offline `SearchDocument` pack (no LLM) |
| `golden_retrieval_benchmark.json` | Golden questions aligned to the seed pack |

Load with `evaluation.dataset_loader.BenchmarkDatasetLoader` or the CLIs
documented in [`../COLLECTION_EVALUATION.md`](../COLLECTION_EVALUATION.md).

Before trusting scores, ensure `expected_*` identifiers exist in your local
`drawing_search.db` (`manage_dataset.py validate-benchmark`).
