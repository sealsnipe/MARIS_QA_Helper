from __future__ import annotations

from pathlib import Path

from app.document_assets import SavedDocumentImage, format_image_block, save_document_image
from app.loaders.vision_ocr import merge_ocr_blocks, run_vision_ocr


def test_format_image_block_uses_bild_tags() -> None:
    block = format_image_block(image_id="img_001", page=2, transcription="Tabelleninhalt")
    assert block.startswith('[BILD id="img_001" seite="2"]')
    assert block.endswith("[/BILD]")
    assert "Tabelleninhalt" in block


def test_save_document_image_writes_file(tmp_path: Path) -> None:
    assets_dir = tmp_path / "images"
    saved = save_document_image(
        assets_dir,
        image_id="img_001",
        page=1,
        data=b"\x89PNG\r\n\x1a\n" + b"x" * 600,
        mime_type="image/png",
    )
    assert saved.filename == "img_001.png"
    assert (assets_dir / "img_001.png").is_file()


def test_merge_ocr_blocks_appends_bild_sections() -> None:
    merged = merge_ocr_blocks("Fliesstext.", ['[BILD id="img_001"]\nOCR\n[/BILD]'])
    assert "Fliesstext." in merged
    assert "[BILD id=\"img_001\"]" in merged
    assert "[/BILD]" in merged


def test_run_vision_ocr_saves_images_and_formats_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.loaders.vision_ocr.extract_embedded_images",
        lambda *_args, **_kwargs: [
            __import__("app.loaders.vision_ocr", fromlist=["EmbeddedImage"]).EmbeddedImage(
                index=1,
                page=1,
                data=b"\x89PNG\r\n\x1a\n" + b"x" * 600,
                mime_type="image/png",
            )
        ],
    )
    monkeypatch.setattr(
        "app.loaders.vision_ocr.transcribe_image",
        lambda *_args, **_kwargs: "Transkribierter Inhalt aus Vision",
    )

    result = run_vision_ocr(tmp_path / "doc.pdf", ".pdf", assets_dir=tmp_path / "images")
    assert result.images_processed == 1
    assert result.saved_images[0].filename == "img_001.png"
    assert result.blocks[0].startswith('[BILD id="img_001" seite="1"]')
    assert (tmp_path / "images" / "img_001.png").is_file()
