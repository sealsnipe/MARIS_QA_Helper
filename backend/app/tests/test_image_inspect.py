from __future__ import annotations

from io import BytesIO
from pathlib import Path

from docx import Document as DocxDocument
from PIL import Image

from app.loaders.image_inspect import inspect_document_bytes
from app.upload import build_extraction_meta, inspect_upload


def test_inspect_docx_without_images(tmp_path: Path) -> None:
    path = tmp_path / "plain.docx"
    document = DocxDocument()
    document.add_paragraph("Nur Text ohne Bilder mit ausreichend Zeichen.")
    document.save(path)

    result = inspect_document_bytes(path.read_bytes(), ".docx")
    assert result.has_images is False
    assert result.image_count == 0


def test_inspect_docx_with_image(monkeypatch) -> None:
    class FakeRel:
        target_ref = "media/image1.png"

        class target_part:
            blob = b"x" * 600

    class FakePart:
        rels = {"rId1": FakeRel()}

    class FakeDoc:
        part = FakePart()
        paragraphs = []

    monkeypatch.setattr("app.loaders.image_inspect.DocxDocument", lambda _stream: FakeDoc())
    result = inspect_document_bytes(b"fake-docx", ".docx")
    assert result.has_images is True
    assert result.image_count == 1


def test_inspect_standalone_png(tmp_path: Path) -> None:
    buffer = BytesIO()
    Image.new("RGB", (220, 220), color="green").save(buffer, format="PNG")
    content = buffer.getvalue()
    result = inspect_document_bytes(content, ".png")
    assert result.has_images is True
    assert result.image_count == 1
    assert result.text_extractable is False


def test_inspect_upload_txt_has_no_images() -> None:
    payload = inspect_upload(b"Textdatei mit genug Inhalt.", "notes.txt")
    assert payload["has_images"] is False
    assert payload["image_count"] == 0


def test_inspect_upload_png_has_preview(tmp_path: Path) -> None:
    buffer = BytesIO()
    Image.new("RGB", (220, 220), color="green").save(buffer, format="PNG")
    payload = inspect_upload(buffer.getvalue(), "screenshot.png")
    assert payload["has_images"] is True
    assert payload["image_only"] is True
    assert len(payload["images"]) == 1
    assert payload["images"][0]["preview_data_url"].startswith("data:image/")


def test_build_extraction_meta_partial() -> None:
    meta = build_extraction_meta(image_count=3, images_processed=0, vision_used=False)
    assert '"coverage": "partial"' in meta
    assert '"image_count": 3' in meta


def test_build_extraction_meta_full_after_vision() -> None:
    meta = build_extraction_meta(image_count=2, images_processed=2, vision_used=True)
    assert '"coverage": "full"' in meta
    assert '"vision_used": true' in meta
