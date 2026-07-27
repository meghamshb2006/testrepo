# Engineering Drawing Intelligence PoC

Proof-of-concept for analysing mechanical engineering drawings and indexing
them for keyword and BM25 retrieval.

## Purpose

Upload or ingest PDF engineering drawings, extract structured metadata and
dimensions with a vision-capable model, flatten the rich analysis into a
search index, and retrieve relevant drawings with FTS5 and BM25 ranking.

## Architecture

```
PDF
 -> app.renderer
 -> app.analyzer
 -> app.schemas.DrawingAnalysis
 -> search.services.SearchDocumentBuilder
 -> search.repositories.SearchRepository
 -> SQLite / FTS5 (drawing_search.db)
 -> BM25 (rank-bm25)
 -> search.context.ContextBuilder
```

The FastAPI app (`app/main.py`) provides upload and analyse endpoints. The
search ingestion CLI (`ingest_drawing.py`) uses the same renderer and analyser
pipeline to populate the retrieval index.

## Database separation

| Database | Purpose |
|----------|---------|
| `data/engineering_drawings.db` | Original rich analysis, document metadata, and optional vector chunks (`app/storage/vector_store.py`) |
| `data/drawing_search.db` | Flattened retrieval index with FTS5 full-text search |

These databases are intentionally separate. The search index is derived from
`DrawingAnalysis` and optimised for keyword retrieval; the engineering
drawings database stores the full structured analysis payload.

## Folder structure

```
app/
  analyzer.py          Vision analysis (single OpenAI-compatible client)
  renderer.py          PDF to PNG rendering
  schemas.py           Canonical DrawingAnalysis schema
  main.py              FastAPI upload/analyse API
  config.py            Environment configuration
  storage.py           Uploaded document storage
  storage/vector_store.py  Rich analysis / vector database (engineering_drawings.db)
search/
  database.py          Search SQLite schema
  models/search_document.py
  repositories/search_repository.py
  services/search_document_builder.py
  services/drawing_ingestion_service.py  Thin orchestration over app pipeline
  services/nltk_processor.py
  engines/bm25_engine.py
  context/context_builder.py
tests/
  search/              Unit tests for search components
  integration/         End-to-end ingestion tests
scripts/               Utility scripts for embeddings and vector store setup
ingest_drawing.py      CLI to ingest a PDF into the search index
```

## Setup (Windows PowerShell)

```powershell
cd C:\Users\azureuser\Desktop\engineering-drawing-poc
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m nltk.downloader punkt
Copy-Item .env.example .env
# Edit .env and set OPENAI_API_KEY and OPENAI_MODEL
```

## Environment variables

See `.env.example`. Key variables:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | API key for the vision analysis client |
| `OPENAI_BASE_URL` | OpenAI-compatible API base URL |
| `OPENAI_MODEL` | Vision-capable model name |
| `DRAWING_DATABASE_PATH` | Path to rich analysis database (default: `data/engineering_drawings.db`) |
| `SEARCH_DATABASE_PATH` | Path to search index database (default: `data/drawing_search.db`) |
| `EMBEDDING_API_KEY` | Optional embedding API key |
| `EMBEDDING_BASE_URL` | Optional embedding API base URL |
| `EMBEDDING_MODEL` | Optional embedding model name |

## Run tests

```powershell
python -m compileall app search tests
pytest -q
```

## Ingest a PDF

```powershell
python ingest_drawing.py path\to\drawing.pdf
```

Optional database override:

```powershell
python ingest_drawing.py path\to\drawing.pdf --db-path data\drawing_search.db
```

## Search indexed drawings

After ingestion, use the repository FTS search or BM25 engine from Python:

```python
from search.database import SearchDatabase
from search.repositories.search_repository import SearchRepository
from search.engines.bm25_engine import BM25SearchEngine
from search.services.nltk_processor import NLTKProcessor

db = SearchDatabase()
db.initialize()
repo = SearchRepository(db)

# FTS5 keyword search
hits = repo.search_fts("aluminium AND 6061-T6")

# BM25 ranking
engine = BM25SearchEngine(repo, NLTKProcessor())
engine.build_index()
ranked = engine.search("aluminium 6061-T6 bracket", top_k=5)

db.close()
```

## Run the API

```powershell
uvicorn app.main:app --reload
```

Endpoints:

- `GET /health`
- `POST /api/documents` - upload PDF and render pages
- `POST /api/documents/{document_id}/analyze` - analyse rendered pages

## Current limitations

- PDF input only
- Vision analysis requires a configured OpenAI-compatible endpoint
- Search index schema is flattened; full rich analysis is not stored in `drawing_search.db`
- Vector embeddings (`sqlite-vec`) are optional and separate from BM25 retrieval
- Multi-page PDFs are analysed in a single vision request (app pipeline behaviour)
- No automatic sync between `engineering_drawings.db` and `drawing_search.db`
