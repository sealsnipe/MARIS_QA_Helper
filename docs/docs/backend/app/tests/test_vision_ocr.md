# `backend/app/tests/test_vision_ocr.py`

**Quellpfad:** `backend/app/tests/test_vision_ocr.py`

## Zweck und logischer Aufbau

Tests für Vision-OCR Pipeline: run, merge blocks, append to pdf/docx text, image save, error handling (vision_failed).

## Abhängigkeiten und Traces

- **Importiert / nutzt:** `app.loaders.vision_ocr`, `app.loaders.image_inspect`, test fixtures (images in pdf/docx), fake vision? 
- **Wird genutzt von:** upload (process_images), loaders
- **Daten:** temp uploads + images/

## (Optional) Tests

- run_vision_ocr: blocks + saved_images + counts.
- append/merge: placeholders + transcribed text in output.
- No images / disabled → graceful.
- Failure path → vision_failed UploadError.
