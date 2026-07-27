import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.analyzer import analyze_drawing
from app.renderer import render_pdf
from app.schemas import DrawingAnalysisResponse
from app.storage import save_uploaded_pdf


app = FastAPI(
    title="Engineering Drawing Intelligence API",
    version="0.2.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )

    try:
        document_id, pdf_path, pages_dir = save_uploaded_pdf(file)

        pages = await run_in_threadpool(
            render_pdf,
            pdf_path,
            pages_dir,
        )

        return {
            "document_id": document_id,
            "page_count": len(pages),
            "status": "success",
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Document upload failed: {exc}",
        ) from exc


@app.post(
    "/api/documents/{document_id}/analyze",
    response_model=DrawingAnalysisResponse,
)
async def analyze_document(document_id: str):
    document_dir = Path("data") / "documents" / document_id
    pages_dir = document_dir / "pages"
    analysis_path = document_dir / "analysis.json"

    if not document_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Document '{document_id}' was not found.",
        )

    if not pages_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="Rendered pages directory was not found.",
        )

    page_paths = sorted(
        [
            path
            for path in pages_dir.iterdir()
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        ]
    )

    if not page_paths:
        raise HTTPException(
            status_code=404,
            detail="No rendered drawing pages were found.",
        )

    try:
        analysis = await run_in_threadpool(
            analyze_drawing,
            page_paths,
        )

        response = DrawingAnalysisResponse(
            document_id=document_id,
            status="success",
            analysis=analysis,
        )

        analysis_path.write_text(
            json.dumps(
                response.model_dump(mode="json"),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        return response

    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Drawing analysis failed: {exc}",
        ) from exc