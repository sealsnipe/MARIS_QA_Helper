from __future__ import annotations

from pathlib import Path

from docx import Document as DocxDocument

from app.loaders.errors import LoaderError


def load_docx(path: Path) -> str:
    try:
        document = DocxDocument(str(path))
        parts = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        text = "\n\n".join(parts).strip()
    except Exception as exc:
        raise LoaderError("extraction_failed") from exc

    if not text:
        raise LoaderError("extraction_failed")
    return text
