from __future__ import annotations

from pathlib import Path

from app.loaders.docx_loader import load_docx
from app.loaders.errors import LoaderError
from app.loaders.pdf_loader import load_pdf
from app.loaders.text_loaders import load_text_file


def load_document(path: Path, extension: str) -> str:
    ext = extension.lower()
    if ext in {".txt", ".md"}:
        return load_text_file(path)
    if ext == ".pdf":
        return load_pdf(path)
    if ext == ".docx":
        return load_docx(path)
    raise LoaderError("unsupported_file_type")


def source_type_for_extension(extension: str) -> str:
    ext = extension.lower().lstrip(".")
    if ext in {"txt", "md", "pdf", "docx"}:
        return ext
    return "file"


__all__ = ["LoaderError", "load_document", "source_type_for_extension"]
