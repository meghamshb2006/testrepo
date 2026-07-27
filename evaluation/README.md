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

## Adapting the sample dataset

1. Ingest your drawings.
2. Query the index to confirm `drawing_id`, `drawing_number`, and `filename`.
3. Update `expected_*` fields in the JSON.
4. Re-run retrieval-only evaluation until Hit@k / MRR look sane.
5. Optionally enable `--evaluate-answers` with a controlled model or fake generator.
