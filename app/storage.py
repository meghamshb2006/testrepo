from pathlib import Path
from uuid import uuid4
import shutil

BASE_DIR = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = BASE_DIR / "data" / "documents"


def save_uploaded_pdf(uploaded_file) -> tuple[str, Path, Path]:
    document_id = f"doc_{uuid4().hex[:12]}"
    document_dir = DOCUMENTS_DIR / document_id
    pages_dir = document_dir / "pages"

    pages_dir.mkdir(parents=True, exist_ok=False)

    pdf_path = document_dir / "original.pdf"

    with pdf_path.open("wb") as output_file:
        shutil.copyfileobj(uploaded_file.file, output_file)

    return document_id, pdf_path, pages_dir
