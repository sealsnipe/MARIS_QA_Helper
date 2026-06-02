from __future__ import annotations

from pathlib import Path

import pytest

from app.loaders import LoaderError, load_document


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_load_txt(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("Hallo Support-Wissen mit genug Text.", encoding="utf-8")
    text = load_document(path, ".txt")
    assert "Support-Wissen" in text


def test_load_md(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    path.write_text("# Titel\n\nMarkdown Inhalt mit ausreichend Zeichen.", encoding="utf-8")
    text = load_document(path, ".md")
    assert "Markdown Inhalt" in text


def test_empty_txt_raises(tmp_path: Path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("   \n", encoding="utf-8")
    with pytest.raises(LoaderError):
        load_document(path, ".txt")


def test_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "image.png"
    path.write_bytes(b"fake")
    with pytest.raises(LoaderError):
        load_document(path, ".png")
