# `backend/app/tests/test_selective_vision.py`

**Quellpfad:** `backend/app/tests/test_selective_vision.py`

## Zweck und logischer Aufbau

Tests für selektive Vision-OCR (image ids aus UI, transcribe nur gewählte, compose mit placeholdern).

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.loaders.vision_ocr`, `app.upload` (transcribe_image_ids), docx/pdf fixtures
- **Wird genutzt von:** upload vision path, tests
- **Daten:** temp files + assets

## (Optional) Tests

- parse_transcribe_image_ids (json/list).
- run_vision_ocr mit/ohne selected ids.
- compose_*: nur transcribierte Blöcke.
- Fallbacks bei no vision.
- _png_bytes fixture: noise (os.urandom) embedded images in DOCX, damit Inspektion sie als meaningful erkennt (nicht als low-info filtert).
