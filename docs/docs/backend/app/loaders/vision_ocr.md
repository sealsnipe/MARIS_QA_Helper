# `backend/app/loaders/vision_ocr.py`

**Quellpfad:** `backend/app/loaders/vision_ocr.py`

## Zweck und logischer Aufbau

Extrahiert Bilder aus PDF/DOCX/Standalone-Dateien, speichert sie auf Disk, führt optional **Vision-OCR** (Codex OAuth oder API-Key) aus und formatiert Ergebnisse als `[BILD id="…"]…[/BILD]`-Blöcke.

Zentrale Funktionen: `extract_embedded_images*`, `save_embedded_images`, `run_vision_ocr`, `compose_docx_with_vision`, `append_pdf_image_blocks`, `merge_ocr_blocks`.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `docx_content`, `document_assets`, `llm.transcribe_image`, `image_inspect`
- **Wird genutzt von:** `upload.py`
- **Daten:** `./data/uploads/{customer_id}/{document_id}/images/img_NNN.ext`

## Funktionen (Auszug)

### `run_vision_ocr(path, extension, assets_dir, *, transcribe_ids=None, saved_images=None)`

- `transcribe_ids=None` → alle Bilder transkribieren (Legacy)
- `transcribe_ids={…}` → nur ausgewählte IDs
- Speichert alle Bilder; setzt `SavedDocumentImage.transcribed`

### `compose_docx_with_vision(path, ocr_result) -> str`

Inline-Zusammensetzung via `compose_docx_text` inkl. Platzhalter für nicht-OCR-Bilder.

### `append_pdf_image_blocks(base_text, path, ocr_result) -> str`

Hängt OCR-Blöcke und Platzhalter in Dokumentreihenfolge an PDF-Text an.

### `_extract_standalone_image(content, extension) -> list[EmbeddedImage]`

Für reine Bild-Uploads (PNG etc.): gibt immer das Bild als wählbares zurück (kein MIN_SIZE Filter mehr). Standalone User-Bilder zählen immer (konsistent zu geändertem Verhalten in image_inspect._inspect_image_file). MIN+Heuristik weiterhin nur für eingebettete Container-Bilder.

## Env

`VISION_ENABLED`, `VISION_MODEL`, `VISION_MAX_IMAGES`, `LLM_AUTH_MODE`

## Siehe auch

[`loaders/docx_content.md`](./docx_content.md), [`document_assets.md`](../document_assets.md), [`llm.md`](../llm.md)

## Änderungen (F1)

Standalone <1KB PNGs werden jetzt korrekt als has_images + mit Preview-Images-List für die UI erkannt (Inspect + Einpflegen Flow).
