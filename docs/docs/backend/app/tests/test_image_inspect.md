# `backend/app/tests/test_image_inspect.py`

**Quellpfad:** `backend/app/tests/test_image_inspect.py`

## Zweck und logischer Aufbau

Tests für Bild-Inspektion (PDF/DOCX/IMAGE): embedded images count, pages, OCR readiness, preview data urls.

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.loaders.image_inspect`, test fixtures (pdf/docx with images), tmp files
- **Wird genutzt von:** upload (inspect + vision), loaders
- **Daten:** temp binaries

## (Optional) Tests

- inspect_document_*: image_count, has_images, pages_with_images. (Standalone small valid PNGs accepted; embedded use noise fixtures for meaningful content.)
- `test_embedded_mini_solid_image_in_docx_is_filtered`: explizit dokumentiert Filter von einfarbigen Mini-Bildern (embedded).
- save_embedded, build_preview_data_url.
- Non-image files → 0.
- Fixtures: noise PNGs via `os.urandom` + `Image.frombytes` für embedded DOCX-Tests (≥200x200, high var → pass _is_meaningful).
