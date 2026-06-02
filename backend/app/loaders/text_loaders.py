from __future__ import annotations

from pathlib import Path

from app.loaders.errors import LoaderError


def load_text_file(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")
    except OSError as exc:
        raise LoaderError("extraction_failed") from exc

    if not text.strip():
        raise LoaderError("extraction_failed")
    return text
