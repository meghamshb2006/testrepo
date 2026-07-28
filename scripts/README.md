# Experimental scripts

Scripts in this folder are **not** part of the core lexical retrieval / Q&A path.

| Script | Notes |
|--------|--------|
| `initialise_milestone4.py` | Legacy/experimental rich DB + sqlite-vec init |
| `test_embeddings.py` | Embedding API connectivity smoke check |
| `test_vector_store.py` | sqlite-vec smoke check |

For day-to-day work, use the root CLIs documented in [`../README.md`](../README.md):

- `ingest_drawing.py` / `ingest_dataset.py`
- `ask_drawing.py`
- `evaluate_drawings.py`
- `manage_dataset.py`
- `run_regression_benchmark.py`
- `stress_test_retrieval.py`
- `rebuild_search_index.py`
- `retrieval_health_report.py`
