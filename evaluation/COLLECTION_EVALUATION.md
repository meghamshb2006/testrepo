# Evaluating New Drawing Collections

This runbook prepares the existing lexical retrieval stack for validation
against new engineering drawing sets **before Hermes integration**.

It does **not** change BM25, confidence math, or ranking.

## Goals

1. Bulk-ingest a drawing collection into `drawing_search.db`
2. Validate index integrity and benchmark readiness
3. Run regression and stress checks
4. Produce human-readable reports

## Recommended workflow

### 1. Bulk ingest PDFs

```bash
python ingest_dataset.py /path/to/drawings \
  --database data/drawing_search.db \
  --skip-existing \
  --output-json reports/bulk_ingest.json
```

Notes:

- Requires the same analyzer/API configuration as single-file `ingest_drawing.py`
- Use `--limit N` for smoke runs
- Use `--stop-on-error` for strict CI-style failure

### 2. Offline golden seed (no LLM)

For deterministic local validation, seed prebuilt SearchDocuments:

```bash
python manage_dataset.py seed-documents \
  --database data/drawing_search.db \
  --input evaluation/datasets/golden_seed_documents.json
```

### 3. Dataset management

```bash
python manage_dataset.py count --database data/drawing_search.db
python manage_dataset.py list --database data/drawing_search.db --limit 20
python manage_dataset.py validate-index --database data/drawing_search.db
python manage_dataset.py export-manifest \
  --database data/drawing_search.db \
  --output reports/index_manifest.json
```

Check that a benchmark's expected IDs exist in the index:

```bash
python manage_dataset.py validate-benchmark \
  --database data/drawing_search.db \
  --dataset evaluation/datasets/golden_retrieval_benchmark.json
```

Scaffold a starter benchmark from whatever is currently indexed:

```bash
python manage_dataset.py scaffold-benchmark \
  --database data/drawing_search.db \
  --output evaluation/datasets/local_scaffold_benchmark.json \
  --limit 25
```

Review and enrich scaffolded cases before treating them as golden.

### 4. Rebuild FTS after schema upgrades

```bash
python rebuild_search_index.py --database data/drawing_search.db
```

### 5. Regression benchmark

First run (creates baseline):

```bash
python run_regression_benchmark.py \
  --dataset evaluation/datasets/golden_retrieval_benchmark.json \
  --database data/drawing_search.db \
  --update-baseline reports/baselines/golden_retrieval_baseline.json \
  --output-json reports/golden_current.json \
  --output-markdown reports/golden_current.md \
  --output-csv reports/golden_current.csv
```

Later runs (fail on regressions):

```bash
python run_regression_benchmark.py \
  --dataset evaluation/datasets/golden_retrieval_benchmark.json \
  --database data/drawing_search.db \
  --baseline-json reports/baselines/golden_retrieval_baseline.json \
  --max-regression 0.05 \
  --output-json reports/golden_current.json
```

### 6. Stress test latency

```bash
python stress_test_retrieval.py \
  --dataset evaluation/datasets/golden_retrieval_benchmark.json \
  --database data/drawing_search.db \
  --iterations 5 \
  --output-json reports/retrieval_stress.json \
  --fail-above-p95-ms 250
```

### 7. Health report

```bash
python retrieval_health_report.py \
  --database data/drawing_search.db \
  --probe-query "DR-1001" \
  --benchmark-json reports/golden_current.json \
  --output-markdown reports/retrieval_health.md
```

## Adapting a new collection

1. Ingest PDFs with `ingest_dataset.py` (or seed offline documents).
2. Export a manifest and confirm drawing IDs / numbers.
3. Scaffold a benchmark, then manually add material/revision/standard cases.
4. Run `validate-benchmark` until expectations resolve in the index.
5. Establish a baseline with `run_regression_benchmark.py --update-baseline`.
6. Keep the baseline under `reports/baselines/` (gitignored by default) or a
   reviewed copy under `evaluation/baselines/` if you want it versioned.
7. Re-run regression + stress after any retrieval/index change.

## Golden fixtures in this repo

| File | Purpose |
|------|---------|
| `evaluation/datasets/golden_seed_documents.json` | Offline SearchDocument pack |
| `evaluation/datasets/golden_retrieval_benchmark.json` | Golden retrieval questions aligned to the seed pack |
| `evaluation/datasets/retrieval_intelligence_suites.json` | M7.1 confidence/category suite |
| `evaluation/datasets/sample_benchmark.json` | Generic M6 template |

## Backward compatibility

- Existing `ingest_drawing.py` and `evaluate_drawings.py` remain unchanged in behaviour.
- New CLIs are additive.
- Retrieval ranking, BM25, and confidence estimation are not modified by this milestone.
