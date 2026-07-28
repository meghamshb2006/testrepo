# Engineering Drawing Intelligence

Proof-of-concept backend for **Johnson Electric** engineering drawing Q&A: ingest PDFs, index extracted drawing knowledge, retrieve evidence with lexical search, and answer questions only from that evidence.

> **Status:** Milestones 1–7.3 complete (feature-complete lexical PoC). Milestone 8 is repository hardening and documentation. **Hermes integration is not included.**

This README is intended to be readable in under 10 minutes. For architecture detail, see [`Architecture.md`](Architecture.md). For validating new drawing collections, see [`evaluation/COLLECTION_EVALUATION.md`](evaluation/COLLECTION_EVALUATION.md).

---

## Problem statement

Engineering drawings contain dense identifiers (drawing numbers, revisions, materials, GD&T, standards). Generic search and unconstrained LLMs often miss exact notation or invent unsupported answers.

This project:

1. Extracts structured drawing knowledge into a searchable index.
2. Retrieves evidence with engineering-aware **lexical** retrieval (FTS5 + BM25).
3. Grounds answers in retrieved context and refuses when evidence is weak or missing.

---

## High-level architecture

```text
PDF → render → analyze → SearchDocument → SQLite + FTS5
                                              ↓
Question → preprocess → FTS candidates → BM25 → identifier boost
         → confidence → context → grounded QA (optional LLM)
```

No LangChain / LlamaIndex. Vector / hybrid retrieval is reserved for future Hermes work.

See [`Architecture.md`](Architecture.md) for diagrams and component interaction.

---

## Repository structure

```text
engineering-drawing-poc/
├── app/                      # PDF render, analysis, schemas, config
├── search/                   # Index, retrieval, QA, diagnostics
├── evaluation/               # Benchmarks, metrics, reports, runbooks
├── tests/                    # Unit + integration tests
├── scripts/                  # Experimental / legacy helpers (not core path)
├── ingest_drawing.py         # Single PDF ingest
├── ingest_dataset.py         # Bulk PDF ingest
├── ask_drawing.py            # Grounded Q&A CLI
├── evaluate_drawings.py      # Evaluation CLI
├── manage_dataset.py         # Index / benchmark dataset management
├── run_regression_benchmark.py
├── stress_test_retrieval.py
├── rebuild_search_index.py
├── retrieval_health_report.py
├── Architecture.md
└── README.md
```

| Area | Where to look |
|------|----------------|
| Canonical analysis schema | `app/schemas.py` |
| Search index + FTS | `search/database.py`, `search/repositories/` |
| Retrieval pipeline | `search/services/retrieval_service.py` |
| Benchmarks / golden data | `evaluation/datasets/` |
| Collection validation runbook | `evaluation/COLLECTION_EVALUATION.md` |
| Generated reports | `reports/` (gitignored; create locally) |

---

## Core capabilities

- **Ingestion:** PDF → pages → structured `DrawingAnalysis` → `SearchDocument` → SQLite/FTS5
- **Lexical retrieval:** query preprocessing, FTS5 candidates, BM25 rerank, exact-identifier boost, confidence + explanation, structured context
- **Grounded QA:** answer only from retrieved context; refuse on empty/low-confidence evidence
- **Observability:** optional retrieval traces, diagnostics, health/reindex tooling
- **Validation:** bulk ingest, dataset CLI, regression baselines, stress latency tests, golden fixtures

---

## Retrieval pipeline overview

1. **Preprocess** engineering query (normalize revisions, materials, standards, IDs).
2. **FTS5** selects a candidate pool.
3. **BM25** reranks candidates (engineering-aware tokenisation).
4. **Exact identifier boost** reorders exact ID matches (does not change BM25 scores).
5. **Confidence** estimates HIGH / MEDIUM / LOW with human-readable explanation.
6. **ContextBuilder** formats evidence for the LLM (or for eval-only runs).

Developer diagnostics (`include_trace=True`) add traces and score breakdowns **without** changing ranking.

---

## Typical workflow

1. Configure `.env` (API key + model).
2. Ingest one PDF or a folder of drawings.
3. Ask a question with `ask_drawing.py`.
4. Seed/validate golden data and run evaluation / regression / stress as needed.

---

## Running the project

### Prerequisites

- Python 3.11+ recommended (3.14 works in this clone’s venv)
- OpenAI-compatible API access for analysis and answer generation

### Install

```bash
cd engineering-drawing-poc
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # fill OPENAI_API_KEY and OPENAI_MODEL
```

### Configuration (`.env`)

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Required for analysis / answers |
| `OPENAI_BASE_URL` | Optional custom endpoint |
| `OPENAI_MODEL` | Analysis model |
| `OPENAI_ANSWER_MODEL` | Optional QA model (defaults to `OPENAI_MODEL`) |
| `SEARCH_DATABASE_PATH` | Default `data/drawing_search.db` |
| `RETRIEVAL_OBSERVABILITY_LOGGING` | `true` to enable structured retrieval logs |

### Ingest a single drawing

```bash
python ingest_drawing.py path/to/drawing.pdf
```

### Ask a question

```bash
python ask_drawing.py "What material is specified for BR-1001?"
python ask_drawing.py "Find drawing DR-1001" --json
```

No LLM call is made when retrieval finds no usable evidence.

---

## Running evaluation

```bash
python evaluate_drawings.py \
  --dataset evaluation/datasets/golden_retrieval_benchmark.json \
  --database data/drawing_search.db \
  --output-json reports/eval.json \
  --output-markdown reports/eval.md \
  --output-csv reports/eval.csv
```

Retrieval-only mode needs **no** API credentials. Add `--evaluate-answers` only when scoring grounded answers (requires API config).

---

## Running dataset validation

Offline golden seed (no LLM):

```bash
python manage_dataset.py seed-documents \
  --database data/drawing_search.db \
  --input evaluation/datasets/golden_seed_documents.json

python manage_dataset.py validate-benchmark \
  --database data/drawing_search.db \
  --dataset evaluation/datasets/golden_retrieval_benchmark.json

python manage_dataset.py count --database data/drawing_search.db
```

Bulk PDF ingest:

```bash
python ingest_dataset.py /path/to/drawings \
  --database data/drawing_search.db \
  --skip-existing \
  --output-json reports/bulk_ingest.json
```

Full collection runbook: [`evaluation/COLLECTION_EVALUATION.md`](evaluation/COLLECTION_EVALUATION.md).

---

## Running regression benchmarks

```bash
# Establish baseline
python run_regression_benchmark.py \
  --dataset evaluation/datasets/golden_retrieval_benchmark.json \
  --database data/drawing_search.db \
  --update-baseline reports/baselines/golden.json \
  --output-markdown reports/golden_current.md

# Later: fail if metrics drop more than 5 points
python run_regression_benchmark.py \
  --dataset evaluation/datasets/golden_retrieval_benchmark.json \
  --database data/drawing_search.db \
  --baseline-json reports/baselines/golden.json \
  --max-regression 0.05
```

---

## Running stress tests

```bash
python stress_test_retrieval.py \
  --dataset evaluation/datasets/golden_retrieval_benchmark.json \
  --database data/drawing_search.db \
  --iterations 5 \
  --output-json reports/stress.json \
  --fail-above-p95-ms 250
```

---

## Testing

```bash
python -m pytest -q
```

Expect **128+** tests, all offline (no live LLM required for the suite).

---

## Current project status

| Milestone | Scope | Status |
|-----------|--------|--------|
| 1–4 | Ingest, schemas, search DB, BM25 foundations | Complete |
| 5 | Grounded QA + two-stage retrieval | Complete |
| 6 | Evaluation framework | Complete |
| 7.1 | Retrieval intelligence (preprocess, boost, confidence) | Complete |
| 7.2 | Observability (traces, diagnostics, health/reindex) | Complete |
| 7.3 | Dataset readiness (bulk ingest, regression, stress, golden) | Complete |
| 8 | Hardening & documentation | This milestone |
| Hermes | MCP / enterprise integration | **Not started** |

---

## Future Hermes integration

Planned (out of scope here):

- Hermes / MCP tool surface over this backend
- Optional semantic embeddings and hybrid retrieval (e.g. sqlite-vec + RRF)
- Production auth, tenancy, and operational monitoring

Until then, treat this repo as a **validated lexical retrieval + grounded QA PoC** that another engineer can clone, evaluate, and extend.

---

## Related docs

- [`Architecture.md`](Architecture.md) — architecture diagrams and component overview
- [`evaluation/README.md`](evaluation/README.md) — metrics, confidence formula, observability
- [`evaluation/COLLECTION_EVALUATION.md`](evaluation/COLLECTION_EVALUATION.md) — new collection validation runbook
