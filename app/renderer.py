import pymupdf
from pathlib import Path


def render_pdf(pdf_path: Path, pages_dir: Path):
    document = pymupdf.open(pdf_path)

    rendered_pages = []

    for page_number, page in enumerate(document, start=1):
        pix = page.get_pixmap(dpi=200)

        image_path = pages_dir / f"page_{page_number:03}.png"

        pix.save(image_path)

        rendered_pages.append(image_path)

    document.close()

    return rendered_pages
