from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from app.loaders.errors import LoaderError


def load_pdf(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            if extracted.strip():
                parts.append(extracted)
        text = "\n\n".join(parts).strip()
    except Exception as exc:
        raise LoaderError("extraction_failed") from exc

    if not text:
        raise LoaderError("extraction_failed")
    return text
