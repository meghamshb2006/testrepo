# Milestone 6 Evaluation Framework

Reusable evaluation for engineering drawing retrieval and grounded answering.

## Purpose

Measure:

- retrieval quality (Hit@1 / Hit@3 / Hit@5, MRR)
- grounded answer term recall and source accuracy
- refusal behaviour for unanswerable questions
- latency (mean and p95)
- regressions via CLI thresholds

Evaluation works **without live API calls by default** (retrieval-only mode).

## Dataset schema

JSON file validated by `evaluation.schemas.BenchmarkDataset`.

Top-level fields:

- `name`
- `version`
- `description` (optional)
- `cases` (list of `BenchmarkCase`)

Each case may include:

- `case_id`, `question`
- `expected_drawing_ids`, `expected_drawing_numbers`, `expected_filenames`
- `expected_answer_terms`, `forbidden_answer_terms`
- `answerable` (default `true`)
- `category`, `notes`
- optional overrides: `candidate_limit`, `top_k`, `max_context_characters`

See `evaluation/datasets/sample_benchmark.json` for an example template.

## Creating benchmark cases

1. Index drawings into `drawing_search.db` with known IDs.
2. Copy the sample dataset and replace `expected_*` fields with your real
   drawing identifiers.
3. Keep unanswerable cases with `answerable: false` and empty expected IDs.
4. Prefer exact engineering notation in `expected_answer_terms`
   (`6061-T6`, `ISO-2768`, `BR-1001`).

## Retrieval metrics

| Metric | Meaning |
|--------|---------|
| Hit@k | At least one expected identifier appears in the top-k retrieved identifiers |
| MRR | Mean reciprocal rank of the first matching identifier |

Identifiers are matched case-insensitively with whitespace collapsed.
Engineering punctuation (`-`, `/`, `.`, `+`) is preserved.

## Answer metrics

| Metric | Meaning |
|--------|---------|
| Answer term recall | Fraction of expected answer terms found in the answer text |
| Source accuracy | Answerable cases where a returned source matches an expected identifier |
| Refusal accuracy | Unanswerable cases with a correct grounded=False refusal |
| Grounded response rate | Fraction of answer cases with `grounded=True` |

Answer scoring is **deterministic term matching**. It does not use an LLM judge.
Paraphrased correct answers may score poorly if expected terms are missing.

## Refusal evaluation

For `answerable=false`, a correct refusal requires:

- `grounded=False`
- answer text containing phrases such as
  "does not contain enough information",
  "cannot be determined",
  "insufficient context"

## CLI commands

Retrieval-only (no API credentials required):

```powershell
python evaluate_drawings.py --dataset evaluation\datasets\sample_benchmark.json --database data\drawing_search.db
```

With answer evaluation:

```powershell
python evaluate_drawings.py --dataset evaluation\datasets\sample_benchmark.json --evaluate-answers
```

Write reports:

```powershell
python evaluate_drawings.py --dataset evaluation\datasets\sample_benchmark.json --output-json reports\evaluation.json --output-markdown reports\evaluation.md
```

Threshold regression checks:

```powershell
python evaluate_drawings.py --dataset benchmark.json --fail-below-hit-at-1 0.8 --fail-below-hit-at-5 0.95 --fail-below-mrr 0.85 --fail-on-case-error
```

## Running without an LLM

Omit `--evaluate-answers`. Only `RetrievalService` is exercised.

## Running with answer evaluation

Pass `--evaluate-answers`. The QA service lazily creates
`DrawingAnswerGenerator` only when retrieval returns evidence, so API
configuration is required for answerable cases that hit indexed drawings.

For automated tests, inject a fake answer generator into
`DrawingQuestionAnsweringService` instead of calling a live model.

## Limitations

- Deterministic term matching is brittle for paraphrase.
- Sample dataset IDs must match your local index.
- Threshold flags are only meaningful after the dataset is aligned.
- No concurrent evaluation in Milestone 6.
- Production M7.1 comparison against a live index requires re-ingest so
  new FTS fields (`revision`, `engineering_standards`, `components`,
  `body`) are populated; additive migration leaves older rows empty for
  those columns until documents are upserted again.

## Retrieval confidence (Milestone 7.1)

`RetrievalConfidenceEstimator` scores each retrieve() call in `[0, 1]`
from weighted deterministic signals:

| Signal | Default weight | Meaning |
|--------|----------------|---------|
| Top BM25 (sigmoid) | 0.25 | Strength of the top hit |
| Top-1 vs top-2 gap (sigmoid) | 0.20 | Separation / ambiguity |
| Exact identifier match | 0.25 | Query ID equals drawing/part/material/standard fields |
| Metadata field hits | 0.15 | Relevant identity fields present on the top hit |
| Result/candidate sanity | 0.10 | Non-empty ranking relative to candidate pool |
| Context quality | 0.05 | Non-empty context, not only `[context truncated]` |

Levels (config overrides via env):

- `HIGH` when score ≥ `RETRIEVAL_CONFIDENCE_HIGH_THRESHOLD` (default `0.80`)
- `MEDIUM` when score ≥ `RETRIEVAL_CONFIDENCE_MEDIUM_THRESHOLD` (default `0.50`)
- `LOW` otherwise

Empty retrieval always yields score `0.0` / `LOW`.

QA treats `confidence_level == LOW` with no exact identifier match as
no-evidence (skips the LLM).

Category suite: `evaluation/datasets/retrieval_intelligence_suites.json`.

Example retrieval-only run:

```bash
python evaluate_drawings.py \
  --dataset evaluation/datasets/retrieval_intelligence_suites.json \
  --database data/drawing_search.db \
  --output-json reports/m71_retrieval_report.json \
  --output-markdown reports/m71_retrieval_report.md \
  --output-csv reports/m71_retrieval_report.csv
```

## Observability (Milestone 7.2)

Developer-facing diagnostics do **not** change ranking.

- `retrieve(..., include_trace=True)` adds `retrieval_trace` with stage
  latencies, identifiers, score breakdowns (annotation-only), and
  confidence explanation.
- Evaluation always requests traces and attaches per-case `diagnostics`.
- Structured logging: set `RETRIEVAL_OBSERVABILITY_LOGGING=true`.
- Rebuild index: `python rebuild_search_index.py --database data/drawing_search.db`
- Health report: `python retrieval_health_report.py --database data/drawing_search.db --output-markdown reports/retrieval_health.md`

Score breakdowns expose `base_bm25_score` / matched fields / tokens.
`final_score` equals BM25; identifier “bonuses” are explanatory only.

## Validation & dataset readiness (Milestone 7.3)

See the full runbook: [`COLLECTION_EVALUATION.md`](COLLECTION_EVALUATION.md).

Additive tooling (no ranking changes):

| CLI | Purpose |
|-----|---------|
| `ingest_dataset.py` | Bulk PDF ingest |
| `manage_dataset.py` | List/count/validate/export/scaffold/seed |
| `run_regression_benchmark.py` | Eval + baseline regression gate |
| `stress_test_retrieval.py` | Latency/throughput stress harness |

Golden fixtures:

- `evaluation/datasets/golden_seed_documents.json`
- `evaluation/datasets/golden_retrieval_benchmark.json`

Reports now include a **Category Breakdown** section when cases set `category`.

## Adapting the sample dataset

1. Ingest your drawings.
2. Query the index to confirm `drawing_id`, `drawing_number`, and `filename`.
3. Update `expected_*` fields in the JSON.
4. Re-run retrieval-only evaluation until Hit@k / MRR look sane.
5. Optionally enable `--evaluate-answers` with a controlled model or fake generator.
