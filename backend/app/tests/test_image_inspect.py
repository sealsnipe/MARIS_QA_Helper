from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

from docx import Document as DocxDocument
from PIL import Image

from app.loaders.image_inspect import inspect_document_bytes
from app.upload import build_extraction_meta, inspect_upload
from app.tests.conftest import create_customer


def _inspect(db_session, content: bytes, filename: str):
    create_customer(db_session, "inspect-test", "Inspect Test")
    return inspect_upload(db_session, "inspect-test", content, filename)


def test_inspect_docx_without_images(tmp_path: Path) -> None:
    path = tmp_path / "plain.docx"
    document = DocxDocument()
    document.add_paragraph("Nur Text ohne Bilder mit ausreichend Zeichen.")
    document.save(path)

    result = inspect_document_bytes(path.read_bytes(), ".docx")
    assert result.has_images is False
    assert result.image_count == 0


def test_inspect_docx_with_image(monkeypatch) -> None:
    """Embedded image fixture now uses blocky structured random (survives 32x32 LANCZOS
    downsample in heuristic) so it passes _is_meaningful_image (strict) for embedded content.
    Small solid / low-info blobs are filtered (see the explicit filter test).
    """
    def _meaningful_test_png_bytes(w: int = 240, h: int = 240) -> bytes:
        im = Image.new("RGB", (w, h))
        block = 8
        for y in range(0, h, block):
            for x in range(0, w, block):
                r = int.from_bytes(os.urandom(1), "big")
                g = int.from_bytes(os.urandom(1), "big")
                b = int.from_bytes(os.urandom(1), "big")
                for yy in range(block):
                    for xx in range(block):
                        if y + yy < h and x + xx < w:
                            im.putpixel((x + xx, y + yy), (r, g, b))
        buf = BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()

    class FakeRel:
        target_ref = "media/image1.png"

        class target_part:
            blob = _meaningful_test_png_bytes(240, 240)

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


def test_inspect_upload_txt_has_no_images(db_session) -> None:
    payload = _inspect(
        db_session,
        b"Dies ist eine Textdatei mit genug Inhalt fuer den Hash.",
        "notes.txt",
    )
    assert payload["has_images"] is False
    assert payload["image_count"] == 0
    assert payload["duplicate"] is None
    assert payload["similar"] == []


def test_inspect_upload_png_has_preview(db_session, tmp_path: Path) -> None:
    buffer = BytesIO()
    Image.new("RGB", (220, 220), color="green").save(buffer, format="PNG")
    payload = _inspect(db_session, buffer.getvalue(), "screenshot.png")
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


def test_embedded_mini_solid_image_in_docx_is_filtered(monkeypatch) -> None:
    """Explicitly documents the filter behavior for embedded low-info images (e.g. solid mini
    deco/backgrounds in DOCX). These must be dropped by MIN + _is_meaningful_image (strict).
    Standalone user-uploaded images bypass size and are accepted if PIL-valid (see other tests).
    """
    # Small solid PNG bytes (low variance, will fail meaningful check even if > MIN after save)
    buf = BytesIO()
    Image.new("RGB", (60, 60), color="red").save(buf, format="PNG")
    tiny_solid_blob = buf.getvalue()

    class FakeRel:
        target_ref = "media/deco.png"

        class target_part:
            blob = tiny_solid_blob

    class FakePart:
        rels = {"rId1": FakeRel()}

    class FakeDoc:
        part = FakePart()
        paragraphs = []

    monkeypatch.setattr("app.loaders.image_inspect.DocxDocument", lambda _stream: FakeDoc())
    result = inspect_document_bytes(b"fake-docx-mini", ".docx")
    assert result.has_images is False
    assert result.image_count == 0
