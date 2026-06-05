from __future__ import annotations

from pathlib import Path

from app.document_assets import SavedDocumentImage, format_image_block, save_document_image
from app.loaders.vision_ocr import OCR_PROMPT, merge_ocr_blocks, parse_ocr_response, run_vision_ocr


def test_ocr_prompt_auto_detects_image_type_without_user_choice() -> None:
    assert "Entscheide SELBST" in OCR_PROMPT
    assert "der Nutzer wählt nicht" in OCR_PROMPT
    assert "FALL A" in OCR_PROMPT
    assert "FALL B" in OCR_PROMPT
    assert "Website-Chrome" in OCR_PROMPT
    assert "Markdown-Tabelle" in OCR_PROMPT
    assert "Verknüpfungen" in OCR_PROMPT
    assert "reicht NICHT" in OCR_PROMPT
    assert "Beziehungen und Ablauf" in OCR_PROMPT
    assert "PERT" not in OCR_PROMPT
    assert "Netzplan" not in OCR_PROMPT
    assert '"mermaid"' in OCR_PROMPT


def test_parse_ocr_response_json_with_mermaid() -> None:
    raw = '{"text": "Ablauf", "mermaid": "flowchart TD\\n  A --> B"}'
    text, mermaid = parse_ocr_response(raw)
    assert text == "Ablauf"
    assert mermaid == "flowchart TD\n  A --> B"


def test_parse_ocr_response_json_without_mermaid() -> None:
    text, mermaid = parse_ocr_response('{"text": "Nur Text", "mermaid": null}')
    assert text == "Nur Text"
    assert mermaid is None


def test_parse_ocr_response_fenced_json() -> None:
    raw = '```json\n{"text": "Inhalt", "mermaid": null}\n```'
    text, mermaid = parse_ocr_response(raw)
    assert text == "Inhalt"
    assert mermaid is None


def test_parse_ocr_response_plain_text_fallback() -> None:
    text, mermaid = parse_ocr_response("Alter Fliesstext ohne JSON")
    assert text == "Alter Fliesstext ohne JSON"
    assert mermaid is None


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
