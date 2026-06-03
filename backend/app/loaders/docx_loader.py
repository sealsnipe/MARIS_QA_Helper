from __future__ import annotations

from pathlib import Path

from app.loaders.docx_content import compose_docx_text, load_docx as load_docx_rich

__all__ = ["load_docx"]


def load_docx(path: Path) -> str:
    return load_docx_rich(path)
